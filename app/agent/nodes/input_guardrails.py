"""Input guardrails node intercepting prompt injection and redacting PII."""

import logging
from typing import Any

from app.agent.guardrails import InputGuardrails
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


class InputGuardrailsNode:
    """Evaluates user query for prompt injection attacks and redacts PII before processing."""

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Scan query, sanitize PII, and block malicious prompt injections."""
        query = state.get("query", "")
        existing_flags = list(state.get("guardrail_flags", []))

        result = InputGuardrails.evaluate_query(query)
        new_flags = existing_flags + result.flags

        if not result.is_safe:
            logger.warning(f"InputGuardrailsNode blocked query: '{query}' (flags: {result.flags})")
            return {
                "query": query,
                "final_answer": result.violation_message,
                "draft_answer": result.violation_message,
                "guardrail_flags": new_flags,
                "provider_used": "guardrails:input",
            }

        return {
            "query": result.sanitized_text,
            "guardrail_flags": new_flags,
        }
