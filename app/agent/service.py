"""High-level Agentic RAG Service wrapping the compiled LangGraph execution."""

import logging
import uuid
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import build_agent_graph
from app.agent.state import AgentState, create_initial_state
from app.retrieval.models import Citation, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)


class AgentService:
    """Orchestrates agentic query execution through the compiled LangGraph workflow."""

    _instance: Any = None

    @classmethod
    def get_instance(cls) -> "AgentService":
        if cls._instance is None:
            cls._instance = AgentService()
        return cls._instance

    def __init__(
        self,
        graph: CompiledStateGraph | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        self.checkpointer = checkpointer or MemorySaver()
        self.graph = graph or build_agent_graph(checkpointer=self.checkpointer)

    async def ainvoke(
        self,
        query: str,
        chat_history: list[BaseMessage] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
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

        config = {}
        if session_id:
            config["configurable"] = {"thread_id": session_id}
        elif user_id:
            config["configurable"] = {"thread_id": f"user_{user_id}"}
        else:
            config["configurable"] = {"thread_id": "default_session"}

        final_state = await self.graph.ainvoke(initial_state, config=config)
        return final_state

    async def answer(self, request: QueryRequest) -> QueryResponse:
        """Execute agentic RAG and return a standard structured QueryResponse."""
        trace_id = str(uuid.uuid4())
        final_state = await self.ainvoke(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            access_level=request.access_level,
            trace_id=trace_id,
        )

        citations = [
            Citation(**c) if isinstance(c, dict) else c
            for c in final_state.get("citations", [])
        ]

        # Post-generation durable user fact extraction
        if request.user_id and final_state.get("final_answer"):
            from app.memory.long_term import UserMemoryService

            try:
                user_mem = UserMemoryService.get_instance()
                extracted = await user_mem.extract_facts(
                    user_message=request.query,
                    assistant_response=final_state.get("final_answer", ""),
                )
                if extracted:
                    await user_mem.async_store_facts(
                        user_id=request.user_id, facts=extracted
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Background fact extraction failed for user '{request.user_id}': {e}"
                )

        return QueryResponse(
            answer=final_state.get("final_answer") or "",
            citations=citations,
            provider_used=final_state.get("provider_used") or "none",
            trace_id=final_state.get("trace_id", trace_id),
        )
