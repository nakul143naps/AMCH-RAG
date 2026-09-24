"""Comprehensive tests for Observability, OpenTelemetry tracing, Prometheus metrics, and Evals."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.state import AgentState, create_initial_state
from app.main import app
from app.observability import (
    LangfuseTracer,
    get_metrics_exposition,
    get_tracer,
    record_cache_hit,
    record_cache_miss,
    record_circuit_breaker_trip,
    record_crag_rewrite,
    record_crag_web_fallback,
    record_gateway_call,
    record_gateway_failover,
    record_groundedness_check,
    record_node_latency,
    setup_tracer,
    trace_span,
    wrap_traced_node,
)
from evals.evaluate import load_golden_dataset, run_evaluation


def test_tracer_setup_and_retrieval():
    """Verify setup_tracer initializes OpenTelemetry tracer provider."""
    tracer = setup_tracer()
    assert tracer is not None
    active_tracer = get_tracer()
    assert active_tracer is not None


@pytest.mark.asyncio
async def test_trace_span_context_manager():
    """Verify trace_span context manager attaches attributes and handles blocks."""
    executed = False
    async with trace_span("test.span", {"test.attr": "value123"}) as span:
        assert span is not None
        executed = True

    assert executed is True


@pytest.mark.asyncio
async def test_trace_span_exception_recording():
    """Verify trace_span records exceptions on failed blocks."""
    with pytest.raises(ValueError, match="Span failure test"):
        async with trace_span("test.failing_span"):
            raise ValueError("Span failure test")


@pytest.mark.asyncio
async def test_wrap_traced_node_success():
    """Verify wrap_traced_node executes node, sets attributes, and captures metrics."""
    async def sample_node(state: AgentState) -> dict:
        return {
            "route": "retrieve",
            "cache_hit": True,
            "groundedness_score": 0.85,
        }

    traced = wrap_traced_node("cache_lookup", sample_node)
    initial_state = create_initial_state(query="What is AMCH-RAG?")
    result = await traced(initial_state)

    assert result["route"] == "retrieve"
    assert result["cache_hit"] is True
    assert result["groundedness_score"] == 0.85


@pytest.mark.asyncio
async def test_wrap_traced_node_exception():
    """Verify wrap_traced_node records exception and re-raises when node fails."""
    async def failing_node(state: AgentState) -> dict:
        raise RuntimeError("Simulated node failure")

    traced = wrap_traced_node("failing_node", failing_node)
    initial_state = create_initial_state(query="Test failure")

    with pytest.raises(RuntimeError, match="Simulated node failure"):
        await traced(initial_state)


def test_prometheus_metrics_recording():
    """Verify Prometheus metrics recording functions and exposition output."""
    record_cache_hit("exact")
    record_cache_miss("semantic")
    record_crag_rewrite()
    record_crag_web_fallback()
    record_groundedness_check(score=0.92, passed=True)
    record_groundedness_check(score=0.35, passed=False)
    record_gateway_call(provider="gemini", purpose="generation", success=True, latency=0.25)
    record_gateway_failover(from_provider="gemini", to_provider="groq")
    record_circuit_breaker_trip(provider="gemini")
    record_node_latency(node_name="test_node", latency=0.05)

    exposition = get_metrics_exposition().decode("utf-8")

    assert "rag_cache_requests_total" in exposition
    assert "rag_crag_rewrites_total" in exposition
    assert "rag_crag_web_fallbacks_total" in exposition
    assert "rag_groundedness_checks_total" in exposition
    assert "rag_groundedness_score" in exposition
    assert "rag_gateway_calls_total" in exposition
    assert "rag_gateway_failovers_total" in exposition
    assert "rag_circuit_breaker_tripped_total" in exposition
    assert "rag_node_latency_seconds" in exposition


@pytest.mark.asyncio
async def test_metrics_api_endpoint():
    """Verify GET /metrics returns 200 with Prometheus exposition format."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        content = response.text
        assert "rag_cache_requests_total" in content


def test_langfuse_tracer_disabled_by_default():
    """Verify LangfuseTracer behaves gracefully as a no-op when credentials are not configured."""
    tracer = LangfuseTracer()
    assert tracer.is_enabled is False
    # Should not raise any error
    tracer.trace_generation(
        name="test_gen",
        model="gemini-2.5-flash",
        prompt="hello",
        completion="world",
    )
    tracer.flush()


def test_langfuse_tracer_mocked():
    """Verify LangfuseTracer calls underlying client when configured."""
    mock_client = MagicMock()
    mock_trace = MagicMock()
    mock_client.trace.return_value = mock_trace

    tracer = LangfuseTracer()
    tracer._enabled = True
    tracer._client = mock_client

    tracer.trace_generation(
        name="generation",
        model="gemini-2.5-pro",
        prompt="Test prompt",
        completion="Test completion",
        trace_id="trace-12345",
        latency_seconds=0.45,
    )

    mock_client.trace.assert_called_once_with(
        id="trace-12345",
        name="amch-rag.generation",
        metadata={},
    )
    mock_trace.generation.assert_called_once()


def test_golden_dataset_integrity():
    """Verify golden dataset contains at least 20 items with complete required schema."""
    dataset = load_golden_dataset()
    assert len(dataset) >= 20, f"Expected at least 20 golden items, got {len(dataset)}"

    seen_ids = set()
    for item in dataset:
        assert "id" in item
        assert "question" in item
        assert "ground_truth" in item
        assert "context" in item
        assert isinstance(item["context"], list)
        assert len(item["context"]) > 0

        # Unique IDs
        assert item["id"] not in seen_ids
        seen_ids.add(item["id"])


@pytest.mark.asyncio
async def test_evaluation_runner_subset(tmp_path: Path):
    """Verify evaluation runner executes on subset and generates valid JSON report."""
    report_file = tmp_path / "test_report.json"
    report = await run_evaluation(limit=3, output_file=report_file)

    assert report["total_evaluated"] == 3
    assert "aggregate_metrics" in report
    assert "faithfulness" in report["aggregate_metrics"]
    assert "answer_relevance" in report["aggregate_metrics"]
    assert "context_recall" in report["aggregate_metrics"]
    assert report_file.exists()

    with open(report_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["total_evaluated"] == 3
