"""Memory node retrieving long-term user facts and short-term dialogue context."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.memory.long_term import UserMemoryService
from app.memory.short_term import ShortTermMemoryManager

logger = logging.getLogger(__name__)


class MemoryNode:
    """Retrieves relevant user facts and injects memory context into AgentState."""

    def __init__(
        self,
        user_memory_service: UserMemoryService | None = None,
        short_term_manager: ShortTermMemoryManager | None = None,
    ) -> None:
        self.user_memory_service = (
            user_memory_service or UserMemoryService.get_instance()
        )
        self.short_term_manager = (
            short_term_manager or ShortTermMemoryManager()
        )

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Fetch user-specific facts and summarize prior history if needed."""
        query = state.get("query", "").strip()
        user_id = state.get("user_id")
        chat_history = state.get("chat_history", [])

        memory_parts = []

        # 1. Short-term dialogue compression if history is long
        if len(chat_history) > self.short_term_manager.max_messages:
            retained_messages, summary = await self.short_term_manager.compress_history(
                chat_history
            )
            if summary:
                memory_parts.append(f"Earlier conversation summary:\n{summary}")
        else:
            retained_messages = chat_history

        # 2. Long-term durable fact retrieval if user_id is provided
        if user_id:
            try:
                facts = self.user_memory_service.search_user_memory(
                    user_id=user_id, query=query, limit=5
                )
                if facts:
                    fact_lines = [f"- {f.fact}" for f in facts]
                    memory_parts.append(
                        f"Remembered facts about user ({user_id}):\n" + "\n".join(fact_lines)
                    )
                    logger.info(
                        f"MemoryNode retrieved {len(facts)} durable facts for user '{user_id}'"
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to retrieve user memory for user '{user_id}': {e}")

        combined_memory = "\n\n".join(memory_parts) if memory_parts else None

        return {
            "memory_context": combined_memory,
            "chat_history": retained_messages,
        }
