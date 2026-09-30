"""Comprehensive tests for Phase 7 Corrective RAG (CRAG)."""

from unittest.mock import AsyncMock

import pytest

from app.agent.graph import build_agent_graph, crag_decision
from app.agent.nodes.cache import CacheLookupNode
from app.agent.nodes.generate import GenerateNode
from app.agent.nodes.grade import GradeNode
from app.agent.nodes.rerank import RerankNode
from app.agent.nodes.retrieve import RetrieveNode
from app.agent.nodes.rewrite import RewriteNode
from app.agent.nodes.router import RouterNode
from app.agent.nodes.web_search import WebSearchNode
from app.agent.service import AgentService
from app.agent.state import create_initial_state
from app.agent.tools.web_search import WebSearchTool
from app.retrieval.models import RetrievedChunk


def _make_dummy_chunk(chunk_id: str, content: str, source: str = "doc1.txt") -> RetrievedChunk:
    """Helper to create dummy RetrievedChunk for testing."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        score=0.9,
        content=content,
        doc_id="doc-1",
        source=source,
        source_type="txt",
        section="Intro",
        page=1,
    )


# -------------------------------------------------------------------------
# 1. Grader Node Unit Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grader_node_evaluates_and_filters():
    """Verify GraderNode grades chunks and filters out irrelevant ones."""
    mock_gateway = AsyncMock()
    # Chunk 1: relevant, Chunk 2: irrelevant, Chunk 3: ambiguous
    mock_gateway.generate.side_effect = [
        ("GRADE: relevant\nREASON: Directly answers the dosage question.", "gemini"),
        ("GRADE: irrelevant\nREASON: Unrelated clinical study on hypertension.", "gemini"),
        ("GRADE: ambiguous\nREASON: Mentions the drug but unclear details.", "gemini"),
    ]

    grader = GradeNode(gateway=mock_gateway)
    chunks = [
        _make_dummy_chunk("c1", "Lisinopril standard starting dosage is 10mg once daily."),
        _make_dummy_chunk("c2", "Hypertension prevalence is 30% among adults globally."),
        _make_dummy_chunk("c3", "ACE inhibitors have variable dosing depending on indications."),
    ]
    state = create_initial_state(query="What is the dosage of lisinopril?")
    state["retrieved_docs"] = chunks

    result = await grader(state)

    assert result["relevance_grades"] == ["relevant", "irrelevant", "ambiguous"]
    # Chunk 2 (irrelevant) filtered out, keeping relevant (c1) and ambiguous (c3)
    assert len(result["retrieved_docs"]) == 2
    assert [c.chunk_id for c in result["retrieved_docs"]] == ["c1", "c3"]


@pytest.mark.asyncio
async def test_grader_node_graceful_fallback_on_error():
    """Verify GraderNode defaults to 'relevant' when LLM call fails."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.side_effect = RuntimeError("LLM rate limit")

    grader = GradeNode(gateway=mock_gateway)
    chunk = _make_dummy_chunk("c1", "Some technical content")
    state = create_initial_state(query="Any question")
    state["retrieved_docs"] = [chunk]

    result = await grader(state)

    assert result["relevance_grades"] == ["relevant"]
    assert len(result["retrieved_docs"]) == 1


# -------------------------------------------------------------------------
# 2. Query Rewriter Node Unit Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rewrite_node_increments_counter_and_rewrites():
    """Verify RewriteNode increments correction_attempts and updates rewritten_query."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.return_value = (
        "lisinopril starting dosage hypertension guidelines",
        "gemini",
    )

    rewriter = RewriteNode(gateway=mock_gateway)
    state = create_initial_state(query="how much pill?")
    assert state["correction_attempts"] == 0

    result = await rewriter(state)

    assert result["correction_attempts"] == 1
    assert result["rewritten_query"] == "lisinopril starting dosage hypertension guidelines"
    assert mock_gateway.generate.called


@pytest.mark.asyncio
async def test_rerank_node_preserves_explicit_query_term_match():
    """Keep a hybrid result containing a queried section when cross-encoder omits it."""
    reranker = AsyncMock()
    top_chunk = _make_dummy_chunk("top", "General resume summary.")
    certification_chunk = _make_dummy_chunk(
        "certifications",
        "Cer tifica tions\nCPBI Certificate: Banking, Finance and Insurance\n"
        "Getting Started with Artificial Intelligence - IBM SkillsBuild",
        source="Vaishnavi_Ningampet_Resume.pdf",
    )
    reranker.async_rerank.return_value = [top_chunk]
    state = create_initial_state(
        query="what are the certifications present in Vaishnavi_Ningampet_Resume.pdf"
    )
    state["retrieved_docs"] = [top_chunk, certification_chunk]

    result = await RerankNode(reranker=reranker)(state)

    assert [chunk.chunk_id for chunk in result["retrieved_docs"]] == [
        "top",
        "certifications",
    ]


# -------------------------------------------------------------------------
# 3. Web Search Node Unit Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_search_node_formats_chunks():
    """Verify WebSearchNode formats web search results into valid RetrievedChunks."""
    mock_tool = AsyncMock(spec=WebSearchTool)
    mock_tool.async_search.return_value = [
        {
            "title": "Quantum Telemetry Explained",
            "url": "https://example.com/quantum",
            "snippet": "Quantum telemetry measures microscopic quantum state observables.",
        }
    ]

    web_node = WebSearchNode(tool=mock_tool)
    state = create_initial_state(query="What is quantum telemetry?")

    result = await web_node(state)

    assert len(result["web_results"]) == 1
    assert len(result["retrieved_docs"]) == 1

    chunk = result["retrieved_docs"][0]
    assert chunk.doc_id == "web_search"
    assert chunk.source_type == "web"
    assert "https://example.com/quantum" in chunk.source
    assert "Quantum Telemetry Explained" in chunk.section
    assert "quantum state observables" in chunk.content


# -------------------------------------------------------------------------
# 4. CRAG Decision Function Logic Tests
# -------------------------------------------------------------------------

def test_crag_decision_routing():
    """Verify crag_decision function adheres strictly to correction bounds and conditions."""
    chunk = _make_dummy_chunk("c1", "Valid content")

    # 1. Documents present -> generate
    state_valid = create_initial_state(query="test")
    state_valid["retrieved_docs"] = [chunk]
    assert crag_decision(state_valid) == "generate"

    # 2. No documents, correction_attempts < MAX (default 2) -> rewrite
    state_retry = create_initial_state(query="test")
    state_retry["retrieved_docs"] = []
    state_retry["correction_attempts"] = 0
    assert crag_decision(state_retry) == "rewrite"

    state_retry["correction_attempts"] = 1
    assert crag_decision(state_retry) == "rewrite"

    # 3. No documents, correction_attempts >= MAX -> web_search fallback
    state_exhausted = create_initial_state(query="test")
    state_exhausted["retrieved_docs"] = []
    state_exhausted["correction_attempts"] = 2
    assert crag_decision(state_exhausted) == "web_search"

    # Explicit references to a resume or filename must not fall back to unrelated web results.
    state_resume = create_initial_state(
        query="what certifications are there in Vaishnavi_Ningampet_Resume.pdf"
    )
    state_resume["correction_attempts"] = 2
    assert crag_decision(state_resume) == "generate"


# -------------------------------------------------------------------------
# 5. End-to-End CRAG Integration Flow Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crag_happy_path_relevant_docs_skip_rewrite_and_web():
    """Verify that when retrieved documents are relevant, CRAG proceeds straight to generation."""
    mock_retriever = AsyncMock()
    mock_retriever.async_retrieve.return_value = [
        _make_dummy_chunk("c1", "Paris is the capital and largest city of France.")
    ]

    mock_gateway = AsyncMock()
    # 1. Router -> retrieve
    # 2. Grader -> relevant
    # 3. Generator -> answer
    mock_gateway.generate.side_effect = [
        ("ROUTE: retrieve\nREASON: Factual query.", "gemini"),
        ("GRADE: relevant\nREASON: Directly answers capital of France.", "gemini"),
        ("Paris is the capital of France [1].", "gemini"),
    ]

    mock_rewriter = AsyncMock()
    mock_web_search = AsyncMock()

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(),
        grade_node=GradeNode(gateway=mock_gateway),
        rewrite_node=RewriteNode(gateway=mock_rewriter),
        web_search_node=WebSearchNode(tool=mock_web_search),
        generate_node=GenerateNode(gateway=mock_gateway),
    )

    agent = AgentService(graph=graph)
    state = await agent.ainvoke(query="What is the capital of France?")

    assert state["route"] == "retrieve"
    assert state["relevance_grades"] == ["relevant"]
    assert len(state["retrieved_docs"]) == 1
    assert state["correction_attempts"] == 0
    assert "Paris" in (state["final_answer"] or "")
    assert len(state["citations"]) == 1

    # Rewriter and web search were never invoked
    mock_rewriter.generate.assert_not_called()
    mock_web_search.async_search.assert_not_called()


@pytest.mark.asyncio
async def test_crag_rewrite_and_retry_loop_success():
    """Verify that irrelevant retrieval triggers rewrite and retry, recovering relevant docs."""
    mock_retriever = AsyncMock()
    # 1st retrieval returns irrelevant chunk, 2nd retrieval returns relevant chunk
    chunk_irrelevant = _make_dummy_chunk("c1", "Unrelated weather report for southern Spain.")
    chunk_relevant = _make_dummy_chunk("c2", "DeepSeek-R1 is an open-weights reasoning model.")

    mock_retriever.async_retrieve.side_effect = [
        [chunk_irrelevant],
        [chunk_relevant],
    ]

    mock_gateway = AsyncMock()
    mock_gateway.generate.side_effect = [
        ("ROUTE: retrieve\nREASON: Technical query.", "gemini"),  # router
        ("GRADE: irrelevant\nREASON: Weather is unrelated.", "gemini"),  # grade pass 1 -> 0 docs kept
        ("deepseek-r1 reasoning model technical specs", "gemini"),  # query rewrite
        ("GRADE: relevant\nREASON: Accurately describes model.", "gemini"),  # grade pass 2 -> 1 doc kept
        ("DeepSeek-R1 is an open-weights reasoning model [1].", "gemini"),  # generation
    ]

    mock_web_tool = AsyncMock()

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(),
        grade_node=GradeNode(gateway=mock_gateway),
        rewrite_node=RewriteNode(gateway=mock_gateway),
        web_search_node=WebSearchNode(tool=mock_web_tool),
        generate_node=GenerateNode(gateway=mock_gateway),
    )

    agent = AgentService(graph=graph)
    state = await agent.ainvoke(query="tell me about deepseek r1")

    # Verify query was rewritten and retried exactly once
    assert state["correction_attempts"] == 1
    assert state["rewritten_query"] == "deepseek-r1 reasoning model technical specs"
    assert len(state["retrieved_docs"]) == 1
    assert state["retrieved_docs"][0].chunk_id == "c2"
    assert "DeepSeek-R1" in (state["final_answer"] or "")

    # Web search fallback was not needed because retry succeeded
    mock_web_tool.async_search.assert_not_called()


@pytest.mark.asyncio
async def test_crag_out_of_corpus_falls_back_to_web_search():
    """Verify out-of-corpus query retries up to bound, then falls back to web search with labeling."""
    mock_retriever = AsyncMock()
    # Knowledge base has 0 relevant information across all attempts
    mock_retriever.async_retrieve.return_value = [
        _make_dummy_chunk("c0", "General company HR policy.")
    ]

    mock_web_tool = AsyncMock(spec=WebSearchTool)
    mock_web_tool.async_search.return_value = [
        {
            "title": "Latest Exoplanet Discovery 2026",
            "url": "https://space.org/exoplanet-2026",
            "snippet": "Astronomers discovered TOI-700 e in the habitable zone.",
        }
    ]

    mock_gateway = AsyncMock()
    mock_gateway.generate.side_effect = [
        ("ROUTE: retrieve\nREASON: Astronomy discovery.", "gemini"),  # router
        ("GRADE: irrelevant\nREASON: HR policy is not astronomy.", "gemini"),  # grade 1
        ("astronomy exoplanet discovery habitable zone", "gemini"),  # rewrite 1
        ("GRADE: irrelevant\nREASON: Still HR policy.", "gemini"),  # grade 2
        ("latest habitable exoplanet discovery", "gemini"),  # rewrite 2
        ("GRADE: irrelevant\nREASON: Still HR policy.", "gemini"),  # grade 3 -> attempts exhausted
        # Generation using web context
        ("Astronomers discovered TOI-700 e in the habitable zone [1].", "gemini"),
    ]

    graph = build_agent_graph(
        router_node=RouterNode(gateway=mock_gateway),
        cache_node=CacheLookupNode(),
        retrieve_node=RetrieveNode(retriever=mock_retriever),
        rerank_node=RerankNode(),
        grade_node=GradeNode(gateway=mock_gateway),
        rewrite_node=RewriteNode(gateway=mock_gateway),
        web_search_node=WebSearchNode(tool=mock_web_tool),
        generate_node=GenerateNode(gateway=mock_gateway),
    )

    agent = AgentService(graph=graph)
    state = await agent.ainvoke(query="What was the latest exoplanet discovered in 2026?")

    # Verify bound was respected (2 attempts)
    assert state["correction_attempts"] == 2
    # Verify web search was invoked
    assert mock_web_tool.async_search.called
    assert state["web_results"] is not None
    assert len(state["web_results"]) == 1

    # Verify clearly labeled web-sourced answer
    assert "[Web-Sourced Answer]" in (state["final_answer"] or "")
    assert "TOI-700 e" in (state["final_answer"] or "")

    # Citations correctly capture web source
    assert len(state["citations"]) == 1
    assert state["citations"][0].doc_id == "web_search"
    assert "https://space.org/exoplanet-2026" in state["citations"][0].source
