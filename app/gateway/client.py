"""Unified Model Gateway with provider failover, exponential backoff, circuit breaker, and purpose-based routing."""

import asyncio
import logging
from typing import Literal, Optional

from app.config import Settings, get_settings
from app.gateway.circuit_breaker import CircuitBreaker
from app.gateway.providers import (
    BaseLLMProvider,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
)

logger = logging.getLogger(__name__)

PurposeType = Literal[
    "generation",
    "grading",
    "routing",
    "groundedness_check",
    "groundedness",
    "query_rewrite",
    "memory_extraction",
    "summarization",
]


class ModelGateway:
    """Centralized gateway for all LLM calls ensuring resilience, circuit breaking, and provider failover."""

    _instance: Optional["ModelGateway"] = None

    @classmethod
    def get_instance(cls, settings: Settings | None = None) -> "ModelGateway":
        if cls._instance is None:
            cls._instance = ModelGateway(settings=settings)
        return cls._instance

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.providers: dict[str, BaseLLMProvider] = {
            "gemini": GeminiProvider(self.settings),
            "groq": GroqProvider(self.settings),
            "openrouter": OpenRouterProvider(self.settings),
        }
        self.circuit_breakers: dict[str, CircuitBreaker] = {
            name: CircuitBreaker(provider_name=name, failure_threshold=3, cooldown_seconds=30.0)
            for name in self.providers
        }
        self.failover_counts: dict[str, int] = {p: 0 for p in self.providers}

    def get_configured_providers(self) -> dict[str, bool]:
        """Return the configuration status of each provider."""
        return {
            name: provider.is_configured() for name, provider in self.providers.items()
        }

    async def generate(
        self,
        prompt: str,
        purpose: PurposeType = "generation",
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_retries_per_provider: int = 2,
    ) -> tuple[str, str]:
        """Execute an LLM call through the failover priority chain with circuit breakers.

        Returns:
            tuple[str, str]: (generated_text, provider_name_used)
        """
        priority = self.settings.PROVIDER_PRIORITY
        last_error: Exception | None = None

        # Choose model tier based on purpose
        model_override: str | None = None
        if purpose == "generation":
            model_override = (
                self.settings.GEMINI_PRO_MODEL
                if self.settings.GEMINI_PRO_MODEL
                else None
            )

        for provider_name in priority:
            provider = self.providers.get(provider_name)
            breaker = self.circuit_breakers.get(provider_name)

            if not provider or not provider.is_configured():
                continue

            # Check circuit breaker before attempting calls
            if breaker and not breaker.can_execute():
                logger.warning(
                    f"ModelGateway: Circuit breaker for {provider_name} is OPEN. Bypassing provider."
                )
                continue

            for attempt in range(max_retries_per_provider):
                try:
                    logger.info(
                        f"Dispatching LLM call for {purpose} to {provider_name} (attempt {attempt + 1})"
                    )
                    text = await provider.generate_text(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature,
                        model_override=model_override if provider_name == "gemini" else None,
                    )
                    if breaker:
                        breaker.record_success()
                    return text, provider_name
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"Call to {provider_name} failed on attempt {attempt + 1}: {e}"
                    )
                    last_error = e
                    self.failover_counts[provider_name] = (
                        self.failover_counts.get(provider_name, 0) + 1
                    )
                    if breaker and attempt == max_retries_per_provider - 1:
                        breaker.record_failure(e)

                    await asyncio.sleep(0.5 * (2**attempt))

        # If all configured providers failed or were tripped by circuit breaker
        configured = [
            p for p, active in self.get_configured_providers().items() if active
        ]
        if not configured:
            raise RuntimeError(
                "No LLM providers are configured with valid API keys. Please set GEMINI_API_KEY in .env."
            )

        raise RuntimeError(
            f"All configured providers ({priority}) failed or are circuit-broken. Last error: {last_error}"
        )

    # Purpose-based convenience methods per RULES.md §4 & TASKS.md Phase 11

    async def grade(
        self, prompt: str, system_instruction: str | None = None, temperature: float = 0.0
    ) -> tuple[str, str]:
        """Convenience method for CRAG grading LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="grading",
            system_instruction=system_instruction,
            temperature=temperature,
        )

    async def route(
        self, prompt: str, system_instruction: str | None = None, temperature: float = 0.0
    ) -> tuple[str, str]:
        """Convenience method for router LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="routing",
            system_instruction=system_instruction,
            temperature=temperature,
        )

    async def check_groundedness(
        self, prompt: str, system_instruction: str | None = None, temperature: float = 0.0
    ) -> tuple[str, str]:
        """Convenience method for Self-RAG groundedness judge calls."""
        return await self.generate(
            prompt=prompt,
            purpose="groundedness_check",
            system_instruction=system_instruction,
            temperature=temperature,
        )

    async def rewrite_query(
        self, prompt: str, system_instruction: str | None = None, temperature: float = 0.3
    ) -> tuple[str, str]:
        """Convenience method for query rewriting LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="query_rewrite",
            system_instruction=system_instruction,
            temperature=temperature,
        )
