"""LangGraph Agentic Orchestration Graph definition and compiler."""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import (
    CacheLookupNode,
    GenerateNode,
    RerankNode,
    RetrieveNode,
    RouterNode,
)
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def route_decision(state: AgentState) -> Literal["cache_lookup", "retrieve"]:
    """Conditional edge router evaluating the state route decision."""
    route = state.get("route")
    if route == "cache":
        return "cache_lookup"
    # memory and tool_call fall back to retrieve in Phase 6 until dedicated sub-graphs are wired
    return "retrieve"


def cache_decision(state: AgentState) -> Literal["__end__", "retrieve"]:
    """Conditional edge evaluating whether cache hit allows terminating early."""
    if state.get("cache_hit", False):
        return END
    return "retrieve"


def build_agent_graph(
    router_node: RouterNode | None = None,
    cache_node: CacheLookupNode | None = None,
    retrieve_node: RetrieveNode | None = None,
    rerank_node: RerankNode | None = None,
    generate_node: GenerateNode | None = None,
) -> CompiledStateGraph:
    """Build and compile the Phase 6 LangGraph agentic RAG workflow."""
    router = router_node or RouterNode()
    cache = cache_node or CacheLookupNode()
    retrieve = retrieve_node or RetrieveNode()
    rerank = rerank_node or RerankNode()
    generate = generate_node or GenerateNode()

    workflow = StateGraph(AgentState)

    # 1. Register Graph Nodes
    workflow.add_node("router", router)
    workflow.add_node("cache_lookup", cache)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("rerank", rerank)
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
    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()
