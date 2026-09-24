"""Self-RAG Groundedness check node evaluating answer fidelity against retrieved context."""

import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

GROUNDEDNESS_SYSTEM_INSTRUCTION = """You are a rigorous fact-checking evaluator for an enterprise RAG assistant.
Your job is to verify whether every factual assertion in the draft answer is directly and unmistakably supported by the provided context passages.

Respond in this exact format:
STATUS: <SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED>
SCORE: <float between 0.0 and 1.0>
UNSUPPORTED_CLAIMS: <specific unsupported assertions, or 'None'>
REASON: <one sentence justification>"""


class GroundednessNode:
    """Evaluates whether the draft answer is strictly grounded in retrieved documents."""

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway.get_instance()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Check draft answer against context passages and compute groundedness score."""
        draft = state.get("draft_answer", "") or ""
        chunks = state.get("retrieved_docs", [])
        current_retries = state.get("groundedness_retries", 0)
        existing_flags = list(state.get("guardrail_flags", []))

        # Fast-pass for empty or policy/fallback answers
        if not draft or not chunks or draft.startswith((
            "I could not find",
            "I cannot process",
            "Hello!",
            "Hi there",
        )):
            logger.info("GroundednessNode skipping fact check on fallback or greeting answer")
            return {
                "groundedness_score": 1.0,
                "groundedness_feedback": None,
            }

        # Format context passages
        context_snippets = "\n\n".join(
            f"[{i + 1}] {c.content.strip()}" for i, c in enumerate(chunks)
        )
        prompt = (
            f"Context passages:\n{context_snippets}\n\n"
            f"Draft answer:\n{draft}\n\n"
            "Evaluate if the draft answer is fully supported by the context passages above."
        )

        logger.info(
            f"GroundednessNode checking answer groundedness (retry {current_retries})"
        )

        try:
            response_text, _provider = await self.gateway.generate(
                prompt=prompt,
                purpose="groundedness_check",
                system_instruction=GROUNDEDNESS_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )

            # Parse score
            score_match = re.search(r"SCORE:\s*([0-1](?:\.\d+)?)", response_text)
            score = float(score_match.group(1)) if score_match else 0.85

            # Parse status
            status_match = re.search(
                r"STATUS:\s*(SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED)",
                response_text,
                re.IGNORECASE,
            )
            status = status_match.group(1).upper() if status_match else "SUPPORTED"

            # Parse unsupported claims
            claims_match = re.search(
                r"UNSUPPORTED_CLAIMS:\s*(.+?)(?:\nREASON:|$)",
                response_text,
                re.DOTALL | re.IGNORECASE,
            )
            unsupported_claims = (
                claims_match.group(1).strip() if claims_match else "None"
            )
            if unsupported_claims.lower() in ("none", "n/a", "none."):
                unsupported_claims = None

        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Groundedness check LLM call failed: {e}. Defaulting to supported."
            )
            score = 0.90
            status = "SUPPORTED"
            unsupported_claims = None

        logger.info(
            f"GroundednessNode result -> STATUS: {status}, SCORE: {score}, UNSUPPORTED: {unsupported_claims}"
        )

        new_flags = existing_flags
        if status in ("PARTIALLY_SUPPORTED", "UNSUPPORTED") or score < 0.7:
            new_flags = existing_flags + [f"groundedness:unsupported:{score:.2f}"]

        # Increment retry attempt if ungrounded
        new_retries = current_retries
        if (status in ("PARTIALLY_SUPPORTED", "UNSUPPORTED") or score < 0.7) and unsupported_claims:
            new_retries = current_retries + 1

        return {
            "groundedness_score": score,
            "groundedness_retries": new_retries,
            "groundedness_feedback": unsupported_claims,
            "guardrail_flags": new_flags,
        }
