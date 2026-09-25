"""Router node for LangGraph orchestrator deciding query execution path."""

import logging
import re
from typing import Any

from app.agent.state import AgentState, RouteType
from app.cache.service import TwoTierCacheService
from app.gateway.client import ModelGateway
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_INSTRUCTION = """You are an intelligent Self-RAG routing agent deciding whether document retrieval is actually necessary.
Analyze the user query, the conversation context, and the list of available uploaded documents.
Decide the optimal execution route:

- "direct": General knowledge questions, concepts, definitions, explanations, math, programming, general world facts, or advice that do NOT require looking up internal enterprise documents (e.g. "what are transformers", "what is machine learning", "explain photosynthesis", "write python code for fibonacci"). The LLM can answer these directly from its pre-trained knowledge without slow retrieval loops.
- "retrieve": Questions specifically asking for information from uploaded files, internal company documents, proprietary policies, financial reports, or when the user's question relates to the available uploaded internal documents.
- "cache": Any greeting, salutation, or chit-chat (e.g. "hi", "hello", "hey", "how are you", "who are you").
- "memory": Questions answerable purely from known user profile facts or previous conversation history (e.g. "what did I ask earlier", "what is my name").

Respond with your decision in the exact format:
ROUTE: <direct|retrieve|cache|memory>
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

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        cache_service: TwoTierCacheService | None = None,
        vector_mgr: VectorStoreManager | None = None,
    ) -> None:
        self.gateway = gateway or ModelGateway.get_instance()
        self.cache_service = cache_service or TwoTierCacheService.get_instance()
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()

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

        # 1. Fast-path for greetings / pleasantries to save latency & tokens
        if self._is_conversational_greeting(query):
            logger.info(
                f"Router fast-path matched greeting for: '{query}' -> route=cache"
            )
            return {"route": "cache"}

        # 2. Fast-path check: Is this query or an equivalent semantic query already in the cache?
        try:
            cached_entry, hit_type = await self.cache_service.async_lookup(
                query=query, access_level=state.get("access_level", "default")
            )
            if cached_entry:
                logger.info(
                    f"Router detected existing cache hit ({hit_type}) for: '{query}' -> route=cache"
                )
                return {"route": "cache"}
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Router cache probe exception: {e}")

        # 3. Document catalog hint so router knows what documents exist
        doc_catalog_text = "No internal documents currently uploaded in knowledge base."
        try:
            docs = self.vector_mgr.list_documents()
            if docs:
                doc_titles = [d.get("source_name") for d in docs if d.get("source_name")]
                doc_catalog_text = f"Uploaded internal documents available: {doc_titles}"
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Router could not list documents: {e}")

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
            f"{doc_catalog_text}\n\n"
            f"{history_summary}"
            f"User Query: {query}\n\n"
            "Determine the route (direct, retrieve, memory, cache):"
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
        match = re.search(r"route\s*:\s*(direct|cache|memory|retrieve|tool_call)", lower)
        if match:
            return match.group(1)  # type: ignore[return-value]

        # Keyword scan
        if "direct" in lower or "no_retrieval" in lower:
            return "direct"
        if "cache" in lower:
            return "cache"
        if "memory" in lower:
            return "memory"
        if "tool_call" in lower:
            return "tool_call"
        return "retrieve"
