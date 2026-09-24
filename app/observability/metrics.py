"""Prometheus metrics registry and recording utilities for AMCH-RAG."""

import logging

from prometheus_client import (
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

# Cache metrics (Exact vs Semantic, Hit vs Miss)
CACHE_REQUESTS_TOTAL = Counter(
    "rag_cache_requests_total",
    "Total cache requests partitioned by tier (exact/semantic) and status (hit/miss)",
    ["tier", "status"],
)

# CRAG metrics (Correction attempts & Web search fallbacks)
CRAG_REWRITE_ATTEMPTS_TOTAL = Counter(
    "rag_crag_rewrites_total",
    "Total query rewrite attempts triggered during corrective RAG",
)

CRAG_WEB_FALLBACK_TOTAL = Counter(
    "rag_crag_web_fallbacks_total",
    "Total out-of-corpus web search fallback invocations",
)

# Groundedness / Self-RAG metrics
GROUNDEDNESS_CHECKS_TOTAL = Counter(
    "rag_groundedness_checks_total",
    "Total groundedness verification checks partitioned by outcome (passed/failed)",
    ["result"],
)

GROUNDEDNESS_SCORE_HISTOGRAM = Histogram(
    "rag_groundedness_score",
    "Distribution of draft answer groundedness scores",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Model Gateway metrics (Provider usage, status, failover, circuit breaker trips)
GATEWAY_CALLS_TOTAL = Counter(
    "rag_gateway_calls_total",
    "Total gateway provider calls partitioned by provider, purpose, and status",
    ["provider", "purpose", "status"],
)

GATEWAY_FAILOVERS_TOTAL = Counter(
    "rag_gateway_failovers_total",
    "Total provider failovers encountered during LLM calls",
    ["from_provider", "to_provider"],
)

CIRCUIT_BREAKER_TRIPPED_TOTAL = Counter(
    "rag_circuit_breaker_tripped_total",
    "Total circuit breaker trips partitioned by provider",
    ["provider"],
)

# User Feedback metrics
FEEDBACK_TOTAL = Counter(
    "rag_feedback_total",
    "Total user feedback ratings partitioned by value (up/down)",
    ["rating"],
)

# Latency histograms
REQUEST_LATENCY_SECONDS = Histogram(
    "rag_request_latency_seconds",
    "End-to-end API request latency in seconds",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

NODE_LATENCY_SECONDS = Histogram(
    "rag_node_latency_seconds",
    "Execution latency per LangGraph agent node in seconds",
    ["node"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

LLM_LATENCY_SECONDS = Histogram(
    "rag_llm_latency_seconds",
    "Latency of upstream LLM provider calls in seconds",
    ["provider", "purpose"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.5, 5.0, 10.0, 20.0],
)


def record_cache_hit(tier: str = "exact") -> None:
    """Record a cache hit for a specific cache tier."""
    CACHE_REQUESTS_TOTAL.labels(tier=tier, status="hit").inc()


def record_cache_miss(tier: str = "exact") -> None:
    """Record a cache miss for a specific cache tier."""
    CACHE_REQUESTS_TOTAL.labels(tier=tier, status="miss").inc()


def record_crag_rewrite() -> None:
    """Increment the count of query rewrites performed."""
    CRAG_REWRITE_ATTEMPTS_TOTAL.inc()


def record_crag_web_fallback() -> None:
    """Increment the count of fallback searches to the open web."""
    CRAG_WEB_FALLBACK_TOTAL.inc()


def record_groundedness_check(score: float | None, passed: bool) -> None:
    """Record a groundedness check outcome and score."""
    status = "passed" if passed else "failed"
    GROUNDEDNESS_CHECKS_TOTAL.labels(result=status).inc()
    if score is not None:
        GROUNDEDNESS_SCORE_HISTOGRAM.observe(max(0.0, min(1.0, score)))


def record_gateway_call(
    provider: str, purpose: str, success: bool, latency: float | None = None
) -> None:
    """Record a gateway provider invocation with status and latency."""
    status = "success" if success else "error"
    GATEWAY_CALLS_TOTAL.labels(provider=provider, purpose=purpose, status=status).inc()
    if latency is not None and latency >= 0:
        LLM_LATENCY_SECONDS.labels(provider=provider, purpose=purpose).observe(latency)


def record_gateway_failover(from_provider: str, to_provider: str) -> None:
    """Record a failover event between upstream providers."""
    GATEWAY_FAILOVERS_TOTAL.labels(
        from_provider=from_provider, to_provider=to_provider
    ).inc()


def record_circuit_breaker_trip(provider: str) -> None:
    """Record a circuit breaker tripping to the OPEN state."""
    CIRCUIT_BREAKER_TRIPPED_TOTAL.labels(provider=provider).inc()


def record_feedback(rating: str) -> None:
    """Record a user feedback submission."""
    FEEDBACK_TOTAL.labels(rating=rating).inc()


def record_node_latency(node_name: str, latency: float) -> None:
    """Record execution latency for an agent node."""
    if latency >= 0:
        NODE_LATENCY_SECONDS.labels(node=node_name).observe(latency)


def get_metrics_exposition() -> bytes:
    """Generate Prometheus exposition format payload."""
    return generate_latest(REGISTRY)
