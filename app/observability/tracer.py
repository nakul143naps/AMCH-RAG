"""OpenTelemetry tracing setup and LangGraph node instrumentation for AMCH-RAG."""

import functools
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from app.config import get_settings
from app.observability.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_crag_rewrite,
    record_crag_web_fallback,
    record_groundedness_check,
    record_node_latency,
)

logger = logging.getLogger(__name__)

_TRACER_INITIALIZED = False


def setup_tracer() -> trace.Tracer:
    """Initialize OpenTelemetry tracer provider with service resource and optional OTLP exporter."""
    global _TRACER_INITIALIZED
    settings = get_settings()

    if not _TRACER_INITIALIZED:
        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "environment": settings.ENVIRONMENT,
            }
        )
        provider = TracerProvider(resource=resource)

        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(
                    endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT
                )
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info(
                    "OTLP HTTP span exporter enabled: %s",
                    settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to initialize OTLP span exporter: %s", e)

        trace.set_tracer_provider(provider)
        _TRACER_INITIALIZED = True

    return trace.get_tracer(settings.OTEL_SERVICE_NAME)


def get_tracer() -> trace.Tracer:
    """Get the active OpenTelemetry tracer instance."""
    return trace.get_tracer(get_settings().OTEL_SERVICE_NAME)


@asynccontextmanager
async def trace_span(
    name: str, attributes: dict[str, Any] | None = None
) -> AsyncGenerator[trace.Span, None]:
    """Async context manager for creating an active OpenTelemetry span with error handling."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, str(v) if isinstance(v, (dict, list)) else v)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


def wrap_traced_node(node_name: str, node_callable: Any) -> Callable:
    """
    Wrap a LangGraph async node with an OpenTelemetry span, Prometheus metrics, and state tracking.

    Threads state trace_id, tracks latency, and automatically records domain metrics
    (cache hits/misses, CRAG rewrites, web fallbacks, groundedness scores).
    """

    @functools.wraps(node_callable)
    async def traced_node_wrapper(state: Any) -> dict[str, Any]:
        trace_id = state.get("trace_id", "unknown")
        user_id = state.get("user_id") or "anonymous"
        access_level = state.get("access_level", "default")
        tracer = get_tracer()

        span_name = f"node.{node_name}"
        start_time = time.perf_counter()

        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("app.node", node_name)
            span.set_attribute("app.trace_id", trace_id)
            span.set_attribute("app.user_id", user_id)
            span.set_attribute("app.access_level", access_level)

            if "query" in state:
                span.set_attribute("app.query_preview", state["query"][:120])

            try:
                # Execute underlying node logic
                result = await node_callable(state)
            except Exception as e:
                duration = time.perf_counter() - start_time
                record_node_latency(node_name, duration)
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

            duration = time.perf_counter() - start_time
            record_node_latency(node_name, duration)
            span.set_attribute("app.latency_seconds", duration)

            # Record domain-specific metrics & span attributes based on node output
            if isinstance(result, dict):
                if node_name == "cache_lookup":
                    hit = result.get("cache_hit", False)
                    span.set_attribute("app.cache_hit", hit)
                    if hit:
                        record_cache_hit("exact")
                    else:
                        record_cache_miss("exact")

                elif node_name == "rewrite":
                    record_crag_rewrite()
                    span.set_attribute(
                        "app.rewritten_query", str(result.get("rewritten_query", ""))
                    )

                elif node_name == "web_search":
                    record_crag_web_fallback()
                    web_results = result.get("web_results", [])
                    span.set_attribute("app.web_result_count", len(web_results))

                elif node_name == "groundedness_check":
                    score = result.get("groundedness_score")
                    span.set_attribute(
                        "app.groundedness_score", score if score is not None else -1.0
                    )
                    passed = score is not None and score >= 0.70
                    span.set_attribute("app.groundedness_passed", passed)
                    record_groundedness_check(score, passed)

                elif node_name == "router":
                    route = result.get("route")
                    if route:
                        span.set_attribute("app.route", str(route))

                elif node_name == "retrieve":
                    docs = result.get("retrieved_docs", [])
                    span.set_attribute("app.retrieved_docs_count", len(docs))

                elif node_name == "generate":
                    provider = result.get("provider_used")
                    if provider:
                        span.set_attribute("app.provider_used", str(provider))

            span.set_status(Status(StatusCode.OK))
            return result

    return traced_node_wrapper
