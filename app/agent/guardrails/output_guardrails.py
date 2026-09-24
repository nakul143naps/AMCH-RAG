"""Output guardrails for toxicity checks, safety filtering, and citation verification."""

import logging
import re
from typing import NamedTuple

from app.retrieval.models import Citation

logger = logging.getLogger(__name__)

TOXICITY_PATTERNS = [
    r"(?i)\b(kill\s+yourself|commit\s+suicide)\b",
    r"(?i)\b(how\s+to\s+build\s+a\s+(bomb|weapon|explosive))\b",
    r"(?i)\b(synthesize\s+(ricin|anthrax|sarin))\b",
]

CITATION_MARKER_REGEX = re.compile(r"\[(\d+)\]")


class OutputGuardrailResult(NamedTuple):
    is_safe: bool
    verified_answer: str
    verified_citations: list[Citation]
    flags: list[str]


class OutputGuardrails:
    """Verifies generated draft answers for safety, toxicity, and valid citation anchors."""

    @staticmethod
    def check_toxicity(text: str) -> tuple[bool, str | None]:
        """Verify output does not contain prohibited dangerous or toxic patterns."""
        for pattern in TOXICITY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                logger.warning(f"OutputGuardrails detected toxic pattern match: '{match.group(0)}'")
                return True, match.group(0)
        return False, None

    @classmethod
    def verify_citations(
        cls, answer: str, citations: list[Citation]
    ) -> tuple[str, list[Citation], list[str]]:
        """Verify citation markers in text correspond directly to provided citations.

        Strips hallucinated markers that reference non-existent chunk indices.
        """
        flags: list[str] = []
        valid_indices = {c.index for c in citations}

        def _replace_invalid_marker(match: re.Match) -> str:
            idx = int(match.group(1))
            if idx not in valid_indices:
                flags.append(f"citation:hallucinated_index:{idx}")
                logger.warning(
                    f"OutputGuardrails: Stripped hallucinated citation [{idx}] not in valid set {valid_indices}"
                )
                return ""  # Remove hallucinated citation marker
            return match.group(0)

        cleaned_answer = CITATION_MARKER_REGEX.sub(_replace_invalid_marker, answer)
        # Clean up any orphaned double spaces left by removed markers
        cleaned_answer = re.sub(r" +", " ", cleaned_answer).strip()

        # Only retain citations that were actually cited in the text
        cited_indices = {int(m.group(1)) for m in CITATION_MARKER_REGEX.finditer(cleaned_answer)}
        filtered_citations = [c for c in citations if c.index in cited_indices]

        # If model cited nothing but citations exist, keep all citations as relevant references
        if not filtered_citations and citations:
            filtered_citations = citations

        return cleaned_answer, filtered_citations, flags

    @classmethod
    def evaluate_output(
        cls, answer: str, citations: list[Citation]
    ) -> OutputGuardrailResult:
        """Run all output guardrails across the draft answer and citations."""
        flags: list[str] = []

        # 1. Toxicity & Safety Check
        is_toxic, pattern_matched = cls.check_toxicity(answer)
        if is_toxic:
            flags.append(f"toxicity:blocked:{pattern_matched}")
            return OutputGuardrailResult(
                is_safe=False,
                verified_answer="The generated response was blocked by safety policy.",
                verified_citations=[],
                flags=flags,
            )

        # 2. Citation Verification & Normalization
        verified_answer, verified_citations, citation_flags = cls.verify_citations(
            answer, citations
        )
        flags.extend(citation_flags)

        return OutputGuardrailResult(
            is_safe=True,
            verified_answer=verified_answer,
            verified_citations=verified_citations,
            flags=flags,
        )
