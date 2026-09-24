"""Output guardrails node enforcing safety, citation integrity, and final sanitization."""

import logging
from typing import Any

from app.agent.guardrails import OutputGuardrails
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


class OutputGuardrailsNode:
    """Validates final generated answers for citation integrity, safety, and toxicity."""

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Verify citations and toxicity in draft answer, setting final_answer."""
        draft = state.get("draft_answer", "") or ""
        citations = state.get("citations", [])
        existing_flags = list(state.get("guardrail_flags", []))
        groundedness_score = state.get("groundedness_score")
        groundedness_retries = state.get("groundedness_retries", 0)

        # Run output guardrails (citation verification + toxicity scan)
        result = OutputGuardrails.evaluate_output(draft, citations)
        new_flags = existing_flags + result.flags
        final_text = result.verified_answer

        # If groundedness check had exhausted retries with low confidence, add caution note
        if (
            groundedness_score is not None
            and groundedness_score < 0.70
            and groundedness_retries >= 2
            and not final_text.startswith(("[Caution", "I could not", "The generated response"))
        ):
            final_text = (
                "[Caution: Portions of this response could not be fully verified against internal documents]\n"
                f"{final_text}"
            )

        logger.info(
            f"OutputGuardrailsNode completed verification (citations: {len(result.verified_citations)}, flags: {new_flags})"
        )

        return {
            "final_answer": final_text,
            "citations": result.verified_citations,
            "guardrail_flags": new_flags,
        }
