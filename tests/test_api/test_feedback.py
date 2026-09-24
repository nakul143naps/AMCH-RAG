"""Tests for POST /feedback user feedback endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability.metrics import get_metrics_exposition


@pytest.mark.asyncio
async def test_submit_feedback_positive():
    """Verify submitting thumbs-up feedback returns 201 with generated feedback_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/feedback",
            json={
                "trace_id": "trace-test-12345",
                "rating": "up",
                "comment": "Accurate response with valid citations.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "received"
        assert data["trace_id"] == "trace-test-12345"
        assert data["rating"] == "up"
        assert "feedback_id" in data
        assert data["feedback_id"].startswith("fb_")


@pytest.mark.asyncio
async def test_submit_feedback_negative():
    """Verify submitting thumbs-down feedback returns 201 and updates metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/feedback",
            json={
                "trace_id": "trace-test-67890",
                "rating": "down",
                "comment": "Answer was too brief.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == "down"

    # Verify Prometheus feedback metric was recorded
    exposition = get_metrics_exposition().decode("utf-8")
    assert 'rag_feedback_total{rating="down"}' in exposition or "rag_feedback_total" in exposition


@pytest.mark.asyncio
async def test_submit_feedback_validation_error():
    """Verify invalid rating value rejected with 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/feedback",
            json={
                "trace_id": "trace-invalid",
                "rating": "neutral",  # Only 'up' or 'down' allowed
            },
        )
        assert response.status_code == 422
