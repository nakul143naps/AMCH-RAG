"""Router node for LangGraph orchestrator deciding query execution path."""

import logging
import re
from typing import Any

from app.agent.state import AgentState, RouteType
from app.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_INSTRUCTION = """You are an intelligent routing agent for an enterprise knowledge assistant.
Analyze the user query and decide if document retrieval is actually necessary:

- "cache": Choose this for:
  1. Any greeting, salutation, or chit-chat (e.g. "hi", "hii", "hello", "hey", "how are you", "good morning").
  2. Casual pleasantries or acknowledgments (e.g. "thanks", "ok", "cool", "great").
  3. Assistant identity or capability inquiries (e.g. "who are you", "what can you do", "help").
  4. Queries near-identical to a previously answered question.
  DO NOT retrieve documents for greetings or casual conversation.

- "memory": Questions answerable purely from known conversation history or user profile facts without document search.

- "retrieve": Questions requiring factual knowledge retrieval from internal enterprise documents.

- "tool_call": Queries requiring live external web search or calculations.

Respond with your decision in the exact format:
ROUTE: <cache|memory|retrieve|tool_call>
REASON: <one sentence justification>"""

GREETING_PATTERNS = [
    r"^h+i+\b",
    r"^h+e+y+\b",
    r"^h+e+l+l+o+\b",
    r"^(howdy|greetings|hiya|hola|namaste|aloha)\b",
    r"^(yo|sup|wassup|what'?s\s+up)\b",
    r"^good\s+(morning|afternoon|evening|night|day)\b",
    r"^(thank\s*you|thanks|thx|cheers|ty)\b",
    r"^(who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|help(\s+me)?)\b",
    r"^how\s+(are\s+you|are\s+things|is\s+it\s+going|do\s+you\s+do)\b",
]


class RouterNode:
    """Evaluates the user query to choose the optimal downstream node."""

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway.get_instance()

    def _is_conversational_greeting(self, query: str) -> bool:
        """Check if query is a pure conversational greeting or chit-chat."""
        normalized = query.strip().lower()
        if len(normalized) <= 2:
            return True
        for pattern in GREETING_PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Classify user query and set route in AgentState."""
        query = state.get("query", "").strip()

        # Fast-path for greetings / pleasantries to save latency & tokens
        if self._is_conversational_greeting(query):
            logger.info(
                f"Router fast-path matched greeting for: '{query}' -> route=cache"
            )
            return {"route": "cache"}

        # Prepare router prompt with history context if present
        history_summary = ""
        chat_history = state.get("chat_history", [])
        if chat_history:
            recent_turns = chat_history[-4:]
            history_summary = (
                "Recent Conversation:\n"
                + "\n".join(
                    f"- {getattr(msg, 'type', 'message')}: {getattr(msg, 'content', str(msg))}"
                    for msg in recent_turns
                )
                + "\n\n"
            )

        prompt = (
            f"{history_summary}"
            f"User Query: {query}\n\n"
            f"Determine the route (cache, memory, retrieve, tool_call):"
        )

        try:
            response_text, provider = await self.gateway.generate(
                prompt=prompt,
                purpose="routing",
                system_instruction=ROUTER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
            route = self._parse_route(response_text)
            logger.info(f"Router classified query via {provider} -> route={route}")
            return {"route": route}
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Router LLM classification failed ({e}), falling back to 'retrieve'"
            )
            return {"route": "retrieve"}

    def _parse_route(self, text: str) -> RouteType:
        """Extract route decision from LLM text response."""
        lower = text.lower()
        # Look for explicit format first: ROUTE: <route>
        match = re.search(r"route\s*:\s*(cache|memory|retrieve|tool_call)", lower)
        if match:
            return match.group(1)  # type: ignore[return-value]

        # Keyword scan
        if "cache" in lower:
            return "cache"
        if "memory" in lower:
            return "memory"
        if "tool_call" in lower:
            return "tool_call"
        return "retrieve"
