"""Short-term conversation buffer management and token-bounded summarization."""

import logging

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from app.config import get_settings
from app.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = """You are a concise conversation summarizer for an AI assistant.
Compress the following earlier conversation turns into a compact, coherent factual summary.
Retain all specific technical details, user requests, constraints, and assistant answers.
Do not lose key facts or context.

Conversation to summarize:
{conversation_text}

Provide only the concise summary:"""


class ShortTermMemoryManager:
    """Manages conversational history buffers and summarizes earlier turns when budget is exceeded."""

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        max_messages: int | None = None,
    ) -> None:
        self.gateway = gateway or ModelGateway.get_instance()
        settings = get_settings()
        self.max_messages = (
            max_messages
            if max_messages is not None
            else settings.SHORT_TERM_MEMORY_MAX_MESSAGES
        )

    def _format_messages_to_text(self, messages: list[BaseMessage]) -> str:
        """Format a list of LangChain BaseMessage objects into readable dialogue."""
        lines = []
        for msg in messages:
            role = "User"
            if isinstance(msg, AIMessage):
                role = "Assistant"
            elif isinstance(msg, SystemMessage):
                role = "System"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    async def compress_history(
        self,
        messages: list[BaseMessage],
        existing_summary: str | None = None,
    ) -> tuple[list[BaseMessage], str | None]:
        """Check if message count exceeds budget.

        If so, summarize the older messages and retain the most recent ones.
        Returns: (retained_messages, updated_summary)
        """
        if len(messages) <= self.max_messages:
            return messages, existing_summary

        # Split into older messages to compress and recent messages to keep intact
        # Keep the latest half of max_messages
        keep_count = max(2, self.max_messages // 2)
        older_messages = messages[:-keep_count]
        recent_messages = messages[-keep_count:]

        conversation_to_summarize = self._format_messages_to_text(older_messages)
        if existing_summary:
            conversation_to_summarize = (
                f"Previous summary:\n{existing_summary}\n\nNewer turns:\n{conversation_to_summarize}"
            )

        prompt = SUMMARIZATION_PROMPT.format(conversation_text=conversation_to_summarize)
        try:
            summary, _ = await self.gateway.generate(
                prompt=prompt,
                purpose="summarization",
                system_instruction="You are an expert conversation summarizer.",
            )
            updated_summary = summary.strip()
            logger.info(
                f"ShortTermMemory: Compressed {len(older_messages)} messages into summary ({len(updated_summary)} chars). Retained {len(recent_messages)} recent turns."
            )
            return recent_messages, updated_summary
        except Exception as e:  # noqa: BLE001
            logger.warning(f"ShortTermMemory summarization failed: {e}. Keeping messages.")
            return messages, existing_summary
