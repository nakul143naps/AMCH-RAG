"""Unified Model Gateway with provider failover, retries, and purpose-based routing."""

import asyncio
import logging
from typing import Literal, Optional

from app.config import Settings, get_settings
from app.gateway.providers import (
    BaseLLMProvider,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
)

logger = logging.getLogger(__name__)

PurposeType = Literal[
    "generation", "grading", "routing", "groundedness_check", "query_rewrite"
]


class ModelGateway:
    """Centralized gateway for all LLM calls ensuring resilience and provider failover."""

    _instance: Optional["ModelGateway"] = None

    @classmethod
    def get_instance(cls) -> "ModelGateway":
        if cls._instance is None:
            cls._instance = ModelGateway()
        return cls._instance

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.providers: dict[str, BaseLLMProvider] = {
            "gemini": GeminiProvider(self.settings),
            "groq": GroqProvider(self.settings),
            "openrouter": OpenRouterProvider(self.settings),
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
        purpose: PurposeType,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_retries_per_provider: int = 2,
    ) -> tuple[str, str]:
        """
        Execute an LLM call through the failover priority chain.

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
            if not provider or not provider.is_configured():
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
                        model_override=model_override
                        if provider_name == "gemini"
                        else None,
                    )
                    return text, provider_name
                except Exception as e:
                    logger.warning(
                        f"Call to {provider_name} failed on attempt {attempt + 1}: {e}"
                    )
                    last_error = e
                    self.failover_counts[provider_name] = (
                        self.failover_counts.get(provider_name, 0) + 1
                    )
                    await asyncio.sleep(0.5 * (2**attempt))

        # If no configured provider succeeded
        configured = [
            p for p, active in self.get_configured_providers().items() if active
        ]
        if not configured:
            raise RuntimeError(
                "No LLM providers are configured with valid API keys. Please set GEMINI_API_KEY in .env."
            )

        raise RuntimeError(
            f"All configured providers ({priority}) failed. Last error: {last_error}"
        )
