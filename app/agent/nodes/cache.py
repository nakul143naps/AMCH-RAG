"""Cache lookup node checking two-tier exact and semantic vector cache."""

import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.cache.service import TwoTierCacheService
from app.retrieval.models import Citation

logger = logging.getLogger(__name__)

GREETING_PATTERNS = [
    r"^(hi|hello|hey|howdy|greetings)\b",
    r"^good (morning|afternoon|evening|day)\b",
    r"^(thank you|thanks|thx)\b",
    r"^who are you\b",
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
            return {
                "cache_hit": True,
                "final_answer": "Hello! I am your AI assistant. How can I assist you today?",
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
