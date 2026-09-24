"""Input guardrails for prompt-injection detection and PII redaction."""

import logging
import re
from typing import NamedTuple

from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)

# Prompt injection signatures covering direct and indirect attacks
INJECTION_PATTERNS = [
    r"(?i)\b(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|system|earlier)\s+(instructions|prompts|directions|rules)\b",
    r"(?i)\b(you are now|act as|pretend to be)\s+(dan|developer mode|unrestricted|jailbroken|evil ai)\b",
    r"(?i)\b(reveal|show|print|output|display|echo)\s+(your\s+)?(system\s+prompt|initial\s+prompt|developer\s+instruction|internal\s+instructions)\b",
    r"(?i)\b(bypass|disable)\s+(all\s+)?(safety|security|content\s+filters|guardrails)\b",
    r"(?i)\[system\s+override\]",
    r"(?i)system\s*:\s*you\s+(must|are)\b",
    r"(?i)new\s+system\s+instruction\s*:\s*",
]

# PII patterns
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")


class GuardrailCheckResult(NamedTuple):
    is_safe: bool
    sanitized_text: str
    flags: list[str]
    violation_message: str | None = None


class InputGuardrails:
    """Validates user inputs and retrieved documents against prompt injection and PII leaks."""

    @staticmethod
    def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
        """Detect direct or indirect prompt injection patterns in text."""
        for pattern in INJECTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                matched_fragment = match.group(0)
                logger.warning(f"InputGuardrails detected prompt injection pattern: '{matched_fragment}'")
                return True, matched_fragment
        return False, None

    @staticmethod
    def redact_pii(text: str) -> tuple[str, list[str]]:
        """Redact sensitive personally identifiable information (emails, phones, SSNs)."""
        flags: list[str] = []
        redacted = text

        if EMAIL_PATTERN.search(redacted):
            redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
            flags.append("pii:email")

        if PHONE_PATTERN.search(redacted):
            redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
            flags.append("pii:phone")

        if SSN_PATTERN.search(redacted):
            redacted = SSN_PATTERN.sub("[REDACTED_SSN]", redacted)
            flags.append("pii:ssn")

        if CARD_PATTERN.search(redacted):
            redacted = CARD_PATTERN.sub("[REDACTED_CARD]", redacted)
            flags.append("pii:card")

        return redacted, flags

    @classmethod
    def evaluate_query(cls, query: str) -> GuardrailCheckResult:
        """Evaluate and sanitize incoming user query."""
        flags: list[str] = []

        # 1. Prompt injection scan
        is_injection, pattern_matched = cls.detect_prompt_injection(query)
        if is_injection:
            flags.append(f"prompt_injection:user:{pattern_matched}")
            return GuardrailCheckResult(
                is_safe=False,
                sanitized_text=query,
                flags=flags,
                violation_message=(
                    "I cannot process this request because it violates safety guidelines "
                    "(prompt override or system instruction modification detected)."
                ),
            )

        # 2. PII Redaction
        redacted_query, pii_flags = cls.redact_pii(query)
        flags.extend(pii_flags)
        if pii_flags:
            flags.append("pii_redacted")

        return GuardrailCheckResult(
            is_safe=True,
            sanitized_text=redacted_query,
            flags=flags,
            violation_message=None,
        )

    scan_and_sanitize = evaluate_query

    @classmethod
    def sanitize_retrieved_chunk(cls, chunk: RetrievedChunk) -> tuple[RetrievedChunk, list[str]]:
        """Scan and neutralize indirect prompt injections inside retrieved document text."""
        flags: list[str] = []
        is_injection, _pattern_matched = cls.detect_prompt_injection(chunk.content)

        if is_injection:
            logger.warning(
                f"InputGuardrails detected indirect prompt injection in doc '{chunk.doc_id}' chunk '{chunk.chunk_id}'"
            )
            flags.append(f"prompt_injection:document:{chunk.chunk_id}")
            # Neutralize injection by stripping the injection instruction or tagging it as inert
            neutralized_content = (
                f"[SECURITY ALERT: Suspicious instruction in document was neutralized]\n"
                f"{chunk.content}"
            )
            # Remove direct injection matches from document text
            for pattern in INJECTION_PATTERNS:
                neutralized_content = re.sub(
                    pattern, "[NEUTRALIZED_UNTRUSTED_INSTRUCTION]", neutralized_content
                )
            sanitized_chunk = chunk.model_copy(update={"content": neutralized_content})
            return sanitized_chunk, flags

        return chunk, flags
