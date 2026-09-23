"""High-level Agentic RAG Service wrapping the compiled LangGraph execution."""

import logging
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import build_agent_graph
from app.agent.state import AgentState, create_initial_state
from app.retrieval.models import Citation, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)


class AgentService:
    """Orchestrates agentic query execution through the compiled LangGraph workflow."""

    def __init__(self, graph: CompiledStateGraph | None = None) -> None:
        self.graph = graph or build_agent_graph()

    async def ainvoke(
        self,
        query: str,
        chat_history: list[BaseMessage] | None = None,
        user_id: str | None = None,
        access_level: str = "default",
        trace_id: str | None = None,
    ) -> AgentState:
        """Run a query through the LangGraph agent and return the final AgentState."""
        initial_state = create_initial_state(
            query=query,
            trace_id=trace_id or str(uuid.uuid4()),
            chat_history=chat_history,
            user_id=user_id,
            access_level=access_level,
        )

        final_state = await self.graph.ainvoke(initial_state)
        return final_state

    async def answer(self, request: QueryRequest) -> QueryResponse:
        """Execute agentic RAG and return a standard structured QueryResponse."""
        trace_id = str(uuid.uuid4())
        final_state = await self.ainvoke(
            query=request.query,
            access_level=request.access_level,
            trace_id=trace_id,
        )

        citations = [
            Citation(**c) if isinstance(c, dict) else c
            for c in final_state.get("citations", [])
        ]

        return QueryResponse(
            answer=final_state.get("final_answer") or "",
            citations=citations,
            provider_used=final_state.get("provider_used") or "none",
            trace_id=final_state.get("trace_id", trace_id),
        )
