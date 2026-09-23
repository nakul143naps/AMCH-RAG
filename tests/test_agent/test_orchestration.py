"""Comprehensive tests for Phase 6 LangGraph Agentic Orchestration."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qdrant_client import QdrantClient

from app.agent.graph import build_agent_graph, cache_decision, route_decision
from app.agent.nodes.cache import CacheLookupNode
from app.agent.nodes.generate import GenerateNode
from app.agent.nodes.rerank import RerankNode
from app.agent.nodes.retrieve import RetrieveNode
from app.agent.nodes.router import RouterNode
from app.agent.service import AgentService
from app.agent.state import create_initial_state
from app.cache.manager import CacheManager, SQLiteCache
from app.cache.service import TwoTierCacheService
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.models import QueryRequest
from app.retrieval.reranker import RerankerService
from app.retrieval.retriever import HybridRetriever
from app.retrieval.vector_store import VectorStoreManager


def test_agent_state_schema_initialization():
    """Verify AgentState is properly initialized with default values."""
    state = create_initial_state(query="What is AMCH-RAG?")
    assert state["query"] == "What is AMCH-RAG?"
    assert state["trace_id"] is not None
    assert state["chat_history"] == []
    assert state["route"] is None
    assert state["cache_hit"] is False
    assert state["retrieved_docs"] == []
    assert state["relevance_grades"] == []
    assert state["correction_attempts"] == 0
    assert state["final_answer"] is None
    assert state["citations"] == []


@pytest.mark.asyncio
async def test_router_greeting_fast_path():
    """Verify that greetings immediately route to 'cache' without invoking LLM."""
    mock_gateway = AsyncMock()
    router = RouterNode(gateway=mock_gateway)

    for greeting in ["Hello!", "Hi there", "Good morning", "thank you", "who are you"]:
        state = create_initial_state(query=greeting)
        result = await router(state)
        assert result["route"] == "cache"

    # Gateway should not be called at all for fast-path greetings
    mock_gateway.generate.assert_not_called()


@pytest.mark.asyncio
async def test_router_llm_classification():
    """Verify that informational questions are sent to LLM and classified as 'retrieve'."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.return_value = (
        "ROUTE: retrieve\nREASON: Query asks for enterprise medical facts.",
        "gemini",
    )
    router = RouterNode(gateway=mock_gateway)

    state = create_initial_state(query="What are the adverse effects of lisinopril?")
    result = await router(state)

    assert result["route"] == "retrieve"
    assert mock_gateway.generate.called


@pytest.mark.asyncio
async def test_router_fallback_on_error():
    """Verify router gracefully defaults to 'retrieve' if LLM gateway raises an exception."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.side_effect = RuntimeError("Rate limited or unreachable")
    router = RouterNode(gateway=mock_gateway)

    state = create_initial_state(query="Complex enterprise financial query")
    result = await router(state)

    assert result["route"] == "retrieve"


@pytest.mark.asyncio
async def test_cache_node_greeting_immediate_answer():
    """Verify cache node directly produces a conversational greeting response."""
    cache_node = CacheLookupNode()
    state = create_initial_state(query="Hello there!")
    result = await cache_node(state)

    assert result["cache_hit"] is True
    assert "Hello!" in result["final_answer"]
    assert result["provider_used"] == "cache:greeting"
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_cache_node_lookup_hit_and_miss(tmp_path: Path):
    """Verify cache node properly identifies hits and misses in TwoTierCacheService."""
    db_path = str(tmp_path / "agent_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    cache_service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)
    cache_node = CacheLookupNode(cache_service=cache_service)

    # 1. Cache Miss
    state_miss = create_initial_state(query="What is quantum telemetry?")
    miss_res = await cache_node(state_miss)
    assert miss_res["cache_hit"] is False

    # 2. Store in cache
    await cache_service.async_store(
        query="What is quantum telemetry?",
        access_level="default",
        answer="Quantum telemetry measures quantum state observables.",
        citations=[
            {
                "index": 1,
                "source": "quantum.txt",
                "doc_id": "d1",
                "chunk_id": "c1",
                "snippet": "telemetry",
            }
        ],
        doc_ids=["d1"],
        trace_id="trace-test",
    )

    # 3. Cache Hit
    state_hit = create_initial_state(query="what is quantum telemetry?")
    hit_res = await cache_node(state_hit)
    assert hit_res["cache_hit"] is True
    assert (
        hit_res["final_answer"]
        == "Quantum telemetry measures quantum state observables."
    )
    assert len(hit_res["citations"]) == 1
    assert hit_res["citations"][0].source == "quantum.txt"
    assert hit_res["provider_used"] == "cache:exact"


def test_conditional_edges_logic():
    """Verify conditional edge decision functions route states accurately."""
    # Route decision
    assert route_decision({"route": "cache"}) == "cache_lookup"  # type: ignore
    assert route_decision({"route": "retrieve"}) == "retrieve"  # type: ignore
    assert route_decision({"route": "memory"}) == "retrieve"  # type: ignore
    assert route_decision({"route": "tool_call"}) == "retrieve"  # type: ignore

    # Cache decision
    assert cache_decision({"cache_hit": True}) == "__end__"  # type: ignore
    assert cache_decision({"cache_hit": False}) == "retrieve"  # type: ignore


@pytest.mark.asyncio
async def test_graph_greeting_skips_retrieval():
    """Phase 6 acceptance test: a greeting skips retrieval entirely."""
    mock_retriever = AsyncMock()
    mock_reranker = AsyncMock()
    mock_gateway = AsyncMock()

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(reranker=mock_reranker),
        generate_node=GenerateNode(gateway=mock_gateway),
    )

    agent_service = AgentService(graph=graph)
    final_state = await agent_service.ainvoke(query="Hi, good morning!")

    # Verify state outcomes
    assert final_state["route"] == "cache"
    assert final_state["cache_hit"] is True
    assert "Hello!" in (final_state["final_answer"] or "")
    assert final_state["provider_used"] == "cache:greeting"

    # Retrieval, reranking, and generation LLM calls were completely skipped!
    mock_retriever.async_retrieve.assert_not_called()
    mock_reranker.async_rerank.assert_not_called()
    mock_gateway.generate.assert_not_called()


@pytest.mark.asyncio
async def test_graph_cached_question_skips_retrieval(tmp_path: Path):
    """Phase 6 acceptance test: an already-cached question hits cache and skips retrieval."""
    db_path = str(tmp_path / "cached_q.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    cache_service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    # Seed the cache with a previously answered question
    await cache_service.async_store(
        query="What is the capital of France?",
        access_level="default",
        answer="Paris is the capital of France [1].",
        citations=[
            {
                "index": 1,
                "source": "geography.md",
                "doc_id": "geo-1",
                "chunk_id": "c-1",
                "snippet": "Paris",
            }
        ],
        doc_ids=["geo-1"],
        trace_id="seed-trace",
    )

    mock_gateway = AsyncMock()
    # LLM router decides cache because it recognizes repeated/cached question
    mock_gateway.generate.return_value = (
        "ROUTE: cache\nREASON: Already answered.",
        "gemini",
    )

    mock_retriever = AsyncMock()
    mock_reranker = AsyncMock()

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(cache_service=cache_service),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(reranker=mock_reranker),
        generate_node=GenerateNode(gateway=mock_gateway, cache_service=cache_service),
    )

    agent_service = AgentService(graph=graph)
    final_state = await agent_service.ainvoke(query="What is the capital of France?")

    assert final_state["cache_hit"] is True
    assert final_state["final_answer"] == "Paris is the capital of France [1]."
    assert final_state["provider_used"] == "cache:exact"
    assert len(final_state["citations"]) == 1

    # Retrieval and reranking were completely skipped
    mock_retriever.async_retrieve.assert_not_called()
    mock_reranker.async_rerank.assert_not_called()


@pytest.mark.asyncio
async def test_graph_knowledge_base_retrieves_and_generates(tmp_path: Path):
    """Phase 6 acceptance test: a knowledge-base question retrieves, reranks, and generates."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    # Ingest document
    pipeline = IngestionPipeline(vector_mgr=vector_mgr)
    doc_path = tmp_path / "cardiology_protocol.txt"
    doc_path.write_text(
        "Acute coronary syndrome requires immediate administration of aspirin and heparin.",
        encoding="utf-8",
    )
    pipeline.process_file(file_path=doc_path, source_name="cardiology_protocol.txt")

    db_path = str(tmp_path / "kb_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None
    cache_service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    retriever = HybridRetriever(vector_mgr=vector_mgr)
    reranker = RerankerService.get_instance()

    mock_gateway = AsyncMock()
    # First call: router classifying question as 'retrieve'
    # Second call: generator answering with citations
    mock_gateway.generate.side_effect = [
        ("ROUTE: retrieve\nREASON: Medical protocol inquiry.", "gemini"),
        ("Acute coronary syndrome requires aspirin and heparin [1].", "gemini"),
    ]

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(cache_service=cache_service),
        retrieve_node=RetrieveNode(retriever=retriever),
        rerank_node=RerankNode(reranker=reranker),
        generate_node=GenerateNode(gateway=mock_gateway, cache_service=cache_service),
    )

    agent_service = AgentService(graph=graph)
    response = await agent_service.answer(
        QueryRequest(
            query="What is required for acute coronary syndrome?",
            access_level="default",
        )
    )

    assert response.provider_used == "gemini"
    assert "aspirin and heparin" in response.answer
    assert len(response.citations) > 0
    assert response.citations[0].source == "cardiology_protocol.txt"

    # Now verify the result was stored in cache!
    cached_entry, hit_type = await cache_service.async_lookup(
        query="What is required for acute coronary syndrome?", access_level="default"
    )
    assert hit_type == "exact"
    assert cached_entry is not None
    assert "aspirin and heparin" in cached_entry["answer"]


@pytest.mark.asyncio
async def test_graph_empty_retrieval_guard():
    """Verify empty retrieval triggers zero-token fallback cleanly without generating tokens."""
    mock_retriever = AsyncMock()
    mock_retriever.async_retrieve.return_value = []

    mock_gateway = AsyncMock()
    mock_gateway.generate.return_value = ("ROUTE: retrieve", "gemini")

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(),
        generate_node=GenerateNode(gateway=mock_gateway),
    )

    agent_service = AgentService(graph=graph)
    final_state = await agent_service.ainvoke(query="Unknown arcane information")

    assert final_state["retrieved_docs"] == []
    assert "could not find any relevant information" in (
        final_state["final_answer"] or ""
    )
    assert final_state["provider_used"] == "none"
    assert final_state["citations"] == []
