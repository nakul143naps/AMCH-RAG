"""Tests for API health route."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import DIST_DIR, app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Verify that /health returns 200 and expected status schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "qdrant" in data
        assert "cache" in data
        assert "providers" in data
        assert data["qdrant"] is True


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify that / serves the SPA when built, otherwise the API status response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        if DIST_DIR.exists():
            assert response.headers["content-type"].startswith("text/html")
            assert '<div id="root"></div>' in response.text
        else:
            data = response.json()
            assert data["project"] == "AMCH-RAG"
