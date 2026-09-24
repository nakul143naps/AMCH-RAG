"""LangGraph Agentic Orchestration Graph definition with CRAG, Self-RAG Groundedness, and Guardrails."""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import (
    CacheLookupNode,
    GenerateNode,
    GradeNode,
    GroundednessNode,
    InputGuardrailsNode,
    OutputGuardrailsNode,
    RerankNode,
    RetrieveNode,
    RewriteNode,
    RouterNode,
    WebSearchNode,
)
from app.agent.state import AgentState
from app.config import get_settings

logger = logging.getLogger(__name__)


def input_guardrail_decision(state: AgentState) -> Literal["__end__", "router"]:
    """Conditional edge checking whether input guardrail blocked the query."""
    if state.get("provider_used") == "guardrails:input":
        return END
    return "router"


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


def groundedness_decision(state: AgentState) -> Literal["output_guardrails", "generate"]:
    """
    Evaluate Self-RAG groundedness check result:
    - If grounded (score >= 0.70 or no unsupported feedback) -> output_guardrails.
    - If ungrounded and retries < MAX_GROUNDEDNESS_RETRIES -> generate (regeneration retry).
    - If ungrounded and retries >= MAX_GROUNDEDNESS_RETRIES -> output_guardrails (bounded fallback).
    """
    score = state.get("groundedness_score")
    retries = state.get("groundedness_retries", 0)
    settings = get_settings()
    max_retries = settings.MAX_GROUNDEDNESS_RETRIES

    # Fast-path for fallback or greeting answers
    draft = state.get("draft_answer", "") or ""
    if not draft or draft.startswith(("I could not find", "I cannot process", "Hello!", "Hi there")):
        return "output_guardrails"

    if score is not None and score >= 0.70:
        return "output_guardrails"

    # Trigger bounded regeneration if unsupported claims were identified
    if retries < max_retries and state.get("groundedness_feedback"):
        logger.info(
            f"Self-RAG: Groundedness check flagged ungrounded claims (score: {score}), retries {retries} < {max_retries} -> regenerating"
        )
        return "generate"

    logger.info(
        f"Self-RAG: Groundedness retries exhausted ({retries}/{max_retries}) -> routing to output guardrails"
    )
    return "output_guardrails"


def build_agent_graph(
    input_guardrails_node: InputGuardrailsNode | None = None,
    router_node: RouterNode | None = None,
    cache_node: CacheLookupNode | None = None,
    retrieve_node: RetrieveNode | None = None,
    rerank_node: RerankNode | None = None,
    grade_node: GradeNode | None = None,
    rewrite_node: RewriteNode | None = None,
    web_search_node: WebSearchNode | None = None,
    generate_node: GenerateNode | None = None,
    groundedness_node: GroundednessNode | None = None,
    output_guardrails_node: OutputGuardrailsNode | None = None,
) -> CompiledStateGraph:
    """Build and compile the Phase 8 LangGraph RAG workflow with CRAG, Self-RAG, and Guardrails."""
    input_guardrails = input_guardrails_node or InputGuardrailsNode()
    router = router_node or RouterNode()
    cache = cache_node or CacheLookupNode()
    retrieve = retrieve_node or RetrieveNode()
    rerank = rerank_node or RerankNode()
    grader = grade_node or GradeNode()
    rewriter = rewrite_node or RewriteNode()
    web_search = web_search_node or WebSearchNode()
    generate = generate_node or GenerateNode()
    groundedness = groundedness_node or GroundednessNode()
    output_guardrails = output_guardrails_node or OutputGuardrailsNode()

    workflow = StateGraph(AgentState)

    # 1. Register Graph Nodes
    workflow.add_node("input_guardrails", input_guardrails)
    workflow.add_node("router", router)
    workflow.add_node("cache_lookup", cache)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("rerank", rerank)
    workflow.add_node("grade", grader)
    workflow.add_node("rewrite", rewriter)
    workflow.add_node("web_search", web_search)
    workflow.add_node("generate", generate)
    workflow.add_node("groundedness_check", groundedness)
    workflow.add_node("output_guardrails", output_guardrails)

    # 2. Define Directed Flow & Conditional Branches
    # Start -> Input Guardrails
    workflow.add_edge(START, "input_guardrails")

    workflow.add_conditional_edges(
        "input_guardrails",
        input_guardrail_decision,
        {
            END: END,
            "router": "router",
        },
    )

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

    # CRAG Correction loop: query rewrite routes back to retrieve
    workflow.add_edge("rewrite", "retrieve")

    # Web search fallback flows directly into generator
    workflow.add_edge("web_search", "generate")

    # Generator flows into Self-RAG Groundedness check
    workflow.add_edge("generate", "groundedness_check")

    # Self-RAG conditional edge: groundedness verification and bounded regeneration loop
    workflow.add_conditional_edges(
        "groundedness_check",
        groundedness_decision,
        {
            "output_guardrails": "output_guardrails",
            "generate": "generate",
        },
    )

    # Output guardrails flow to END
    workflow.add_edge("output_guardrails", END)

    return workflow.compile()
