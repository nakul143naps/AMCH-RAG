"""LangGraph Agentic Orchestration Graph definition with Corrective RAG (CRAG)."""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import (
    CacheLookupNode,
    GenerateNode,
    GradeNode,
    RerankNode,
    RetrieveNode,
    RewriteNode,
    RouterNode,
    WebSearchNode,
)
from app.agent.state import AgentState
from app.config import get_settings

logger = logging.getLogger(__name__)


def route_decision(state: AgentState) -> Literal["cache_lookup", "retrieve"]:
    """Conditional edge router evaluating the state route decision."""
    route = state.get("route")
    if route == "cache":
        return "cache_lookup"
    # memory and tool_call fall back to retrieve until dedicated sub-graphs are wired
    return "retrieve"


def cache_decision(state: AgentState) -> Literal["__end__", "retrieve"]:
    """Conditional edge evaluating whether cache hit allows terminating early."""
    if state.get("cache_hit", False):
        return END
    return "retrieve"


def crag_decision(state: AgentState) -> Literal["generate", "rewrite", "web_search"]:
    """
    CRAG decision logic evaluating retrieval sufficiency and correction bounds:
    - If retrieved_docs has relevant chunks -> proceed to generate.
    - If no relevant chunks:
        - If correction_attempts < MAX_CORRECTION_ATTEMPTS -> rewrite query and retry retrieval.
        - If correction attempts exhausted -> fallback to web_search or generate zero-context answer.
    """
    settings = get_settings()
    max_attempts = settings.MAX_CORRECTION_ATTEMPTS
    attempts = state.get("correction_attempts", 0)
    docs = state.get("retrieved_docs", [])

    # If relevant/usable documents exist, proceed straight to answer generation
    if docs:
        logger.info(f"CRAG decision: {len(docs)} relevant chunks found -> routing to generate")
        return "generate"

    # If no relevant documents and we have remaining correction attempts -> rewrite & retry
    if attempts < max_attempts:
        logger.info(
            f"CRAG decision: no relevant chunks, attempts {attempts} < {max_attempts} -> routing to rewrite"
        )
        return "rewrite"

    # Correction attempts exhausted: fallback to external web search if enabled
    if settings.ENABLE_WEB_SEARCH_FALLBACK:
        logger.info(
            f"CRAG decision: correction attempts exhausted ({attempts}/{max_attempts}) -> routing to web_search"
        )
        return "web_search"

    logger.info("CRAG decision: correction exhausted and web search disabled -> routing to generate")
    return "generate"


def build_agent_graph(
    router_node: RouterNode | None = None,
    cache_node: CacheLookupNode | None = None,
    retrieve_node: RetrieveNode | None = None,
    rerank_node: RerankNode | None = None,
    grade_node: GradeNode | None = None,
    rewrite_node: RewriteNode | None = None,
    web_search_node: WebSearchNode | None = None,
    generate_node: GenerateNode | None = None,
) -> CompiledStateGraph:
    """Build and compile the Phase 7 LangGraph Corrective RAG workflow."""
    router = router_node or RouterNode()
    cache = cache_node or CacheLookupNode()
    retrieve = retrieve_node or RetrieveNode()
    rerank = rerank_node or RerankNode()
    grader = grade_node or GradeNode()
    rewriter = rewrite_node or RewriteNode()
    web_search = web_search_node or WebSearchNode()
    generate = generate_node or GenerateNode()

    workflow = StateGraph(AgentState)

    # 1. Register Graph Nodes
    workflow.add_node("router", router)
    workflow.add_node("cache_lookup", cache)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("rerank", rerank)
    workflow.add_node("grade", grader)
    workflow.add_node("rewrite", rewriter)
    workflow.add_node("web_search", web_search)
    workflow.add_node("generate", generate)

    # 2. Define Directed Flow & Conditional Branches
    workflow.add_edge(START, "router")

    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "cache_lookup": "cache_lookup",
            "retrieve": "retrieve",
        },
    )

    workflow.add_conditional_edges(
        "cache_lookup",
        cache_decision,
        {
            END: END,
            "retrieve": "retrieve",
        },
    )

    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "grade")

    # CRAG conditional edge: evaluate chunk relevance and loop or fallback
    workflow.add_conditional_edges(
        "grade",
        crag_decision,
        {
            "generate": "generate",
            "rewrite": "rewrite",
            "web_search": "web_search",
        },
    )

    # Correction loop: query rewrite routes back to retrieve
    workflow.add_edge("rewrite", "retrieve")

    # Web search fallback flows directly into grounded generator
    workflow.add_edge("web_search", "generate")

    # Final generation terminates at END
    workflow.add_edge("generate", END)

    return workflow.compile()
