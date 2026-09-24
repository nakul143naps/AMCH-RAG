"""Comprehensive unit, integration, and cross-session tests for Phase 10 Memory."""

import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from qdrant_client import QdrantClient

from app.agent.graph import build_agent_graph
from app.agent.nodes.cache import CacheLookupNode
from app.agent.nodes.generate import GenerateNode
from app.agent.nodes.memory import MemoryNode
from app.agent.nodes.rerank import RerankNode
from app.agent.nodes.retrieve import RetrieveNode
from app.agent.nodes.router import RouterNode
from app.agent.nodes.web_search import WebSearchNode
from app.agent.service import AgentService
from app.agent.state import create_initial_state
from app.memory.long_term import UserMemoryService
from app.memory.short_term import ShortTermMemoryManager
from app.retrieval.models import QueryRequest, RetrievedChunk
from app.retrieval.vector_store import VectorStoreManager


@pytest.fixture
def memory_vector_mgr():
    """Isolated in-memory Qdrant client with user_memory collection."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()
    return vector_mgr


# ---------------------------------------------------------
# Short-Term Memory Tests (Buffer & Summarization)
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_short_term_memory_under_budget():
    """Messages under budget should be preserved intact without summarization."""
    mock_gateway = AsyncMock()
    manager = ShortTermMemoryManager(gateway=mock_gateway, max_messages=6)

    messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there!"),
        HumanMessage(content="What is Kubernetes?"),
        AIMessage(content="Kubernetes is an orchestration platform."),
    ]

    retained, summary = await manager.compress_history(messages)
    assert len(retained) == 4
    assert summary is None
    mock_gateway.generate.assert_not_called()


@pytest.mark.asyncio
async def test_short_term_memory_over_budget_summarization():
    """Messages exceeding budget trigger summarization on older messages while keeping recent turns."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.return_value = (
        "User discussed deploying an e-commerce microservice on AWS with PostgreSQL.",
        "gemini",
    )
    manager = ShortTermMemoryManager(gateway=mock_gateway, max_messages=4)

    messages = [
        HumanMessage(content="Turn 1: We are building an e-commerce store"),
        AIMessage(content="Turn 1 reply: Understood"),
        HumanMessage(content="Turn 2: Database will be PostgreSQL"),
        AIMessage(content="Turn 2 reply: Great choice"),
        HumanMessage(content="Turn 3: Cloud provider will be AWS"),
        AIMessage(content="Turn 3 reply: AWS is recommended"),
        HumanMessage(content="Turn 4: What instance size should we use?"),
    ]

    retained, summary = await manager.compress_history(messages)
    # Kept latest turns
    assert len(retained) < len(messages)
    assert retained[-1].content == "Turn 4: What instance size should we use?"
    assert summary is not None
    assert "e-commerce microservice" in summary
    mock_gateway.generate.assert_called_once()


# ---------------------------------------------------------
# Long-Term User Memory Tests (Extraction & Retrieval)
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_fact_extraction():
    """Test LLM-based durable fact extraction parsing JSON output."""
    mock_gateway = AsyncMock()
    mock_gateway.generate.return_value = (
        json.dumps({
            "facts": [
                "User prefers code solutions in Python",
                "User deployment environment is AWS us-east-1",
            ]
        }),
        "gemini",
    )

    user_mem = UserMemoryService(gateway=mock_gateway)
    facts = await user_mem.extract_facts(
        user_message="Please only give me code in Python. Note that our cloud infra is in AWS us-east-1.",
        assistant_response="Sure, I will stick to Python and us-east-1.",
    )

    assert len(facts) == 2
    assert "User prefers code solutions in Python" in facts
    assert "AWS us-east-1" in facts[1]


def test_user_memory_storage_and_hybrid_search(memory_vector_mgr):
    """Store durable user facts in Qdrant and retrieve them via hybrid search scoped to user_id."""
    user_mem = UserMemoryService(vector_mgr=memory_vector_mgr)

    # Store facts for user A
    user_mem.store_fact(
        user_id="user_alice",
        fact_text="Alice prefers concise bullet points with Python code examples.",
        category="preference",
    )
    user_mem.store_fact(
        user_id="user_alice",
        fact_text="Alice works as a Senior Systems Architect at Acme Corp.",
        category="biographical",
    )

    # Store fact for user B (tenant isolation test)
    user_mem.store_fact(
        user_id="user_bob",
        fact_text="Bob prefers verbose explanations with Java snippets.",
        category="preference",
    )

    # Retrieve memory for Alice
    alice_facts = user_mem.search_user_memory(
        user_id="user_alice",
        query="What language and format does the user prefer?",
        limit=5,
    )
    assert len(alice_facts) > 0
    alice_fact_texts = [f.fact for f in alice_facts]
    assert any("Python" in t for t in alice_fact_texts)
    # Ensure Bob's facts are never leaked to Alice
    assert not any("Java" in t for t in alice_fact_texts)

    # Retrieve all facts
    all_alice = user_mem.get_all_user_facts("user_alice")
    assert len(all_alice) == 2


@pytest.mark.asyncio
async def test_memory_node_execution(memory_vector_mgr):
    """MemoryNode retrieves user facts and injects memory_context into AgentState."""
    user_mem = UserMemoryService(vector_mgr=memory_vector_mgr)
    user_mem.store_fact(
        user_id="user_charlie",
        fact_text="Charlie operates under strict HIPAA compliance rules.",
        category="constraint",
    )

    node = MemoryNode(user_memory_service=user_mem)
    state = create_initial_state(
        query="Can we log patient diagnostic IDs to standard output?",
        user_id="user_charlie",
    )

    update = await node(state)
    assert update["memory_context"] is not None
    assert "HIPAA compliance" in update["memory_context"]
    assert "user_charlie" in update["memory_context"]


# ---------------------------------------------------------
# Phase 10 Acceptance Test: Cross-Session Recall
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_session_memory_recall_acceptance(memory_vector_mgr):
    """Phase 10 Acceptance Criterion:

    A fact stated by the user in Session 1 is remembered and recalled in Session 2,
    guiding the assistant's generation without needing to be repeated.
    """
    user_mem = UserMemoryService(vector_mgr=memory_vector_mgr)

    # SESSION 1: User explicitly states a durable preference/fact
    # Fact extraction captures it and stores it in Qdrant user memory
    user_mem.store_fact(
        user_id="architect_dan",
        fact_text="User's primary database stack is strictly CockroachDB distributed SQL.",
        category="architecture_preference",
    )

    # SESSION 2: New session, completely empty chat history, same user_id
    mock_retriever = AsyncMock()
    mock_retriever.async_retrieve.return_value = [
        RetrievedChunk(
            chunk_id="chunk_1",
            score=0.92,
            content="Database migration guide: Ensure connection pooling is configured for distributed nodes.",
            doc_id="db_guide.md",
            source="db_guide.md",
            source_type="md",
            access_level="default",
            chunk_index=0,
        )
    ]

    mock_gateway = AsyncMock()

    # Capture the prompt passed to generate in Session 2 to verify memory injection
    captured_prompts = []

    async def mock_generate(prompt, purpose="generation", **kwargs):
        captured_prompts.append((purpose, prompt))
        if purpose == "routing":
            return "ROUTE: retrieve", "gemini"
        if purpose == "grading":
            return "DECISION: relevant", "gemini"
        if purpose == "groundedness":
            return "STATUS: SUPPORTED\nSCORE: 0.95", "gemini"
        return (
            "For CockroachDB distributed SQL, configure connection pooling for each distributed node [1].",
            "gemini",
        )

    mock_gateway.generate.side_effect = mock_generate

    from app.agent.nodes.grade import GradeNode
    from app.agent.nodes.groundedness import GroundednessNode

    memory_node = MemoryNode(user_memory_service=user_mem)
    router_node = RouterNode(gateway=mock_gateway)
    retrieve_node = RetrieveNode(retriever=mock_retriever)
    grade_node = GradeNode(gateway=mock_gateway)
    generate_node = GenerateNode(gateway=mock_gateway)
    groundedness_node = GroundednessNode(gateway=mock_gateway)

    graph = build_agent_graph(
        router_node=router_node,
        cache_node=CacheLookupNode(),
        memory_node=memory_node,
        retrieve_node=retrieve_node,
        rerank_node=RerankNode(),
        grade_node=grade_node,
        web_search_node=WebSearchNode(),
        generate_node=generate_node,
        groundedness_node=groundedness_node,
    )

    agent_service = AgentService(graph=graph)

    # Execute Session 2 query
    response = await agent_service.answer(
        QueryRequest(
            query="What connection settings should I configure for my database?",
            user_id="architect_dan",
            session_id="session_2_brand_new_session",
            access_level="default",
        )
    )

    # 1. Answer incorporates the recalled fact
    assert "CockroachDB" in response.answer

    # 2. Verify that the memory context was injected into the generation prompt
    generation_prompt = next(p for pur, p in captured_prompts if pur == "generation")
    assert "User & Conversation Memory" in generation_prompt
    assert "CockroachDB" in generation_prompt
    assert "architect_dan" in generation_prompt
