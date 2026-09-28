"""Unified Model Gateway with provider failover, exponential backoff, circuit breaker, and purpose-based routing."""

import asyncio
import logging
import time
from typing import Literal, Optional

from opentelemetry.trace import Status, StatusCode

from app.config import Settings, get_settings
from app.gateway.circuit_breaker import CircuitBreaker, CircuitState
from app.gateway.providers import (
    BaseLLMProvider,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
)
from app.observability import (
    LangfuseTracer,
    get_tracer,
    record_circuit_breaker_trip,
    record_gateway_call,
    record_gateway_failover,
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
        trace_id: str | None = None,
    ) -> tuple[str, str]:
        """Execute an LLM call through the failover priority chain with circuit breakers and telemetry.

        Returns:
            tuple[str, str]: (generated_text, provider_name_used)
        """
        priority = self.settings.PROVIDER_PRIORITY
        last_error: Exception | None = None
        tracer = get_tracer()
        attempted_failed_providers: list[str] = []

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
                if last_error is None:
                    last_error = RuntimeError(
                        f"Circuit breaker for {provider_name} is in cooldown (OPEN). Please wait ~30s for recovery."
                    )
                continue

            for attempt in range(max_retries_per_provider):
                span_name = f"llm.{provider_name}.{purpose}"
                start_time = time.perf_counter()

                with tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("llm.provider", provider_name)
                    span.set_attribute("llm.purpose", purpose)
                    span.set_attribute("llm.attempt", attempt + 1)
                    if trace_id:
                        span.set_attribute("app.trace_id", trace_id)

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
                        duration = time.perf_counter() - start_time
                        span.set_attribute("llm.latency_seconds", duration)
                        span.set_attribute("llm.response_length", len(text))
                        span.set_status(Status(StatusCode.OK))

                        record_gateway_call(
                            provider=provider_name,
                            purpose=purpose,
                            success=True,
                            latency=duration,
                        )

                        # Record failover metrics if earlier providers in this call failed
                        for prev_p in attempted_failed_providers:
                            record_gateway_failover(prev_p, provider_name)

                        # Trace in Langfuse if enabled
                        langfuse = LangfuseTracer.get_instance()
                        resolved_model = (
                            model_override
                            if (provider_name == "gemini" and model_override)
                            else provider.get_model_name()
                        )
                        langfuse.trace_generation(
                            name=f"{purpose}.{provider_name}",
                            model=resolved_model,
                            prompt=prompt,
                            completion=text,
                            trace_id=trace_id,
                            latency_seconds=duration,
                            metadata={"provider": provider_name, "purpose": purpose},
                        )

                        if breaker:
                            breaker.record_success()
                        return text, provider_name

                    except Exception as e:  # noqa: BLE001
                        duration = time.perf_counter() - start_time
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))

                        record_gateway_call(
                            provider=provider_name,
                            purpose=purpose,
                            success=False,
                            latency=duration,
                        )

                        logger.warning(
                            f"Call to {provider_name} failed on attempt {attempt + 1}: {e}"
                        )
                        last_error = e
                        self.failover_counts[provider_name] = (
                            self.failover_counts.get(provider_name, 0) + 1
                        )
                        if breaker and attempt == max_retries_per_provider - 1:
                            breaker.record_failure(e)
                            if breaker.state == CircuitState.OPEN:
                                record_circuit_breaker_trip(provider_name)
                            if provider_name not in attempted_failed_providers:
                                attempted_failed_providers.append(provider_name)

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
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        trace_id: str | None = None,
    ) -> tuple[str, str]:
        """Convenience method for CRAG grading LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="grading",
            system_instruction=system_instruction,
            temperature=temperature,
            trace_id=trace_id,
        )

    async def route(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        trace_id: str | None = None,
    ) -> tuple[str, str]:
        """Convenience method for router LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="routing",
            system_instruction=system_instruction,
            temperature=temperature,
            trace_id=trace_id,
        )

    async def check_groundedness(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        trace_id: str | None = None,
    ) -> tuple[str, str]:
        """Convenience method for Self-RAG groundedness judge calls."""
        return await self.generate(
            prompt=prompt,
            purpose="groundedness_check",
            system_instruction=system_instruction,
            temperature=temperature,
            trace_id=trace_id,
        )

    async def rewrite_query(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.3,
        trace_id: str | None = None,
    ) -> tuple[str, str]:
        """Convenience method for query rewriting LLM calls."""
        return await self.generate(
            prompt=prompt,
            purpose="query_rewrite",
            system_instruction=system_instruction,
            temperature=temperature,
            trace_id=trace_id,
        )
