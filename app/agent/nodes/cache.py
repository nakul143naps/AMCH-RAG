"""Cache lookup node checking two-tier exact and semantic vector cache."""

import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.cache.service import TwoTierCacheService
from app.retrieval.models import Citation

logger = logging.getLogger(__name__)

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


class CacheLookupNode:
    """Checks the two-tier cache and provides immediate conversational responses for greetings."""

    def __init__(self, cache_service: TwoTierCacheService | None = None) -> None:
        self.cache_service = cache_service or TwoTierCacheService.get_instance()

    def _is_greeting(self, query: str) -> bool:
        normalized = query.strip().lower()
        if len(normalized) <= 2:
            return True
        for pattern in GREETING_PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Execute cache lookup or return immediate response."""
        query = state.get("query", "").strip()
        access_level = state.get("access_level", "default")

        # 1. Immediate conversational greeting response
        if self._is_greeting(query):
            logger.info(f"Cache node matched greeting '{query}' -> instant answer")
            normalized_q = query.strip().lower()
            if "how are you" in normalized_q:
                greeting_reply = "Hello! I'm doing great, thank you for asking! How can I assist you with your research or documents today?"
            elif any(w in normalized_q for w in ["who are you", "what can you do", "help"]):
                greeting_reply = "Hello! I am your AMCH-RAG assistant. You can upload documents in the sidebar to ask questions about them, or ask me any general question!"
            else:
                greeting_reply = "Hello! How can I assist you today?"

            return {
                "cache_hit": True,
                "final_answer": greeting_reply,
                "citations": [],
                "provider_used": "cache:greeting",
            }

        # 2. Check Two-Tier Cache (Exact SHA-256 + Semantic Vector)
        cached_entry, hit_type = await self.cache_service.async_lookup(
            query=query, access_level=access_level
        )

        if cached_entry:
            logger.info(f"Cache hit ({hit_type}) for query: '{query}'")
            citations = [
                Citation(**c) if isinstance(c, dict) else c
                for c in cached_entry.get("citations", [])
            ]
            return {
                "cache_hit": True,
                "final_answer": cached_entry.get("answer", ""),
                "citations": citations,
                "provider_used": f"cache:{hit_type}",
            }

        logger.info(f"Cache miss for query: '{query}'")
        return {"cache_hit": False}
