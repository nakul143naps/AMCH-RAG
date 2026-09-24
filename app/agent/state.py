"""LangGraph State Definition for Agentic RAG."""

import uuid
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

from app.retrieval.models import Citation, RetrievedChunk

RouteType = Literal["cache", "memory", "retrieve", "tool_call", "direct"]
GradeType = Literal["relevant", "ambiguous", "irrelevant"]


class AgentState(TypedDict):
    """Unified state schema threaded through all LangGraph agent nodes."""

    trace_id: str
    query: str
    chat_history: list[BaseMessage]
    user_id: str | None
    access_level: str

    route: RouteType | None
    cache_hit: bool
    memory_context: str | None

    retrieved_docs: list[RetrievedChunk]
    relevance_grades: list[GradeType]
    correction_attempts: int
    rewritten_query: str | None
    web_results: list[dict[str, Any]] | None

    draft_answer: str | None
    citations: list[Citation]
    groundedness_score: float | None
    groundedness_retries: int
    groundedness_feedback: str | None
    guardrail_flags: list[str]

    final_answer: str | None
    provider_used: str | None


def create_initial_state(
    query: str,
    trace_id: str | None = None,
    chat_history: list[BaseMessage] | None = None,
    user_id: str | None = None,
    access_level: str = "default",
) -> AgentState:
    """Create a cleanly initialized AgentState with default values."""
    return AgentState(
        trace_id=trace_id or str(uuid.uuid4()),
        query=query,
        chat_history=chat_history or [],
        user_id=user_id,
        access_level=access_level,
        route=None,
        cache_hit=False,
        memory_context=None,
        retrieved_docs=[],
        relevance_grades=[],
        correction_attempts=0,
        rewritten_query=None,
        web_results=None,
        draft_answer=None,
        citations=[],
        groundedness_score=None,
        groundedness_retries=0,
        groundedness_feedback=None,
        guardrail_flags=[],
        final_answer=None,
        provider_used=None,
    )
