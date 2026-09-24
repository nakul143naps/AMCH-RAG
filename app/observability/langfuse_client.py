"""Langfuse client wrapper for LLM generation tracing, token accounting, and cost tracking."""

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class LangfuseTracer:
    """Singleton wrapper around Langfuse client with safe fallback when credentials are not set."""

    _instance: "LangfuseTracer | None" = None

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)
        self._client: Any = None

        if self._enabled:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse tracing enabled and connected to %s", settings.LANGFUSE_HOST)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to initialize Langfuse client: %s. Tracing disabled.", e)
                self._enabled = False
        else:
            logger.debug("Langfuse tracing disabled (keys not provided).")

    @classmethod
    def get_instance(cls) -> "LangfuseTracer":
        """Return singleton LangfuseTracer instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_enabled(self) -> bool:
        """Check whether Langfuse tracing is active."""
        return self._enabled

    def trace_generation(
        self,
        name: str,
        model: str,
        prompt: str,
        completion: str,
        trace_id: str | None = None,
        latency_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record an LLM generation event in Langfuse.

        Safe no-op if Langfuse is disabled or if an exception occurs during transmission.
        """
        if not self._enabled or self._client is None:
            return

        try:
            trace_obj = self._client.trace(
                id=trace_id,
                name=f"amch-rag.{name}",
                metadata=metadata or {},
            )
            trace_obj.generation(
                name=name,
                model=model,
                input=prompt,
                output=completion,
                metadata={
                    **(metadata or {}),
                    "latency_seconds": latency_seconds,
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Langfuse generation trace failed: %s", e)

    def flush(self) -> None:
        """Flush any pending events to Langfuse."""
        if self._enabled and self._client is not None:
            try:
                self._client.flush()
            except Exception as e:  # noqa: BLE001
                logger.debug("Langfuse flush warning: %s", e)
