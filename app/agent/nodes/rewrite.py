"""Query rewriter node reformulating queries to improve retrieval recall in CRAG loop."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

REWRITER_SYSTEM_INSTRUCTION = """You are an expert search query reformulation assistant.
Given a user query that failed to retrieve relevant documents from the knowledge base,
rewrite the query into an optimized search phrase to retrieve better results.
- Add relevant domain keywords and synonyms.
- Strip conversational filler words.
- Maintain the original search intent.
- Return ONLY the rewritten query text. Do not include markdown, quotes, explanations, or preamble."""


class RewriteNode:
    """Reformulates ambiguous or low-recall queries and increments correction counter."""

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway.get_instance()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Generate a reformulated query and increment correction attempts."""
        current_attempts = state.get("correction_attempts", 0) + 1
        original_query = state.get("query", "").strip()
        last_rewritten = state.get("rewritten_query")
        target_query = last_rewritten or original_query

        prompt = (
            f"Original query: {original_query}\n"
            f"Previous attempt: {target_query}\n\n"
            "The retrieved documents were graded as irrelevant or insufficient.\n"
            "Please rewrite the query to improve retrieval quality:"
        )

        logger.info(
            f"RewriteNode optimizing query: '{original_query}' (attempt {current_attempts})"
        )

        try:
            rewritten_text, _provider = await self.gateway.generate(
                prompt=prompt,
                purpose="query_rewrite",
                system_instruction=REWRITER_SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
            clean_rewritten = rewritten_text.strip().strip('"').strip("'")
            if not clean_rewritten:
                clean_rewritten = original_query
        except Exception as e:  # noqa: BLE001
            logger.warning(f"RewriteNode failed to call LLM gateway: {e}. Keeping current query.")
            clean_rewritten = f"{target_query} overview details"

        logger.info(f"RewriteNode reformulated query into: '{clean_rewritten}'")

        return {
            "correction_attempts": current_attempts,
            "rewritten_query": clean_rewritten,
        }
