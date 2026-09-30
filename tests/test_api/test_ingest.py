"""Tests for ingestion API routes."""

import io
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_ingest
from app.main import app


@pytest.mark.asyncio
async def test_ingest_endpoint_upload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        file_content = b"FastAPI async ingestion pipeline test content. Testing chunking and indexing."
        files = {"file": ("test_doc.txt", io.BytesIO(file_content), "text/plain")}

        # 1. Trigger ingestion
        response = await client.post(
            "/ingest", files=files, data={"access_level": "team_a"}
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["filename"] == "test_doc.txt"
        job_id = data["job_id"]

        # 2. Query job status
        status_resp = await client.get(f"/ingest/{job_id}")
        assert status_resp.status_code == 200
        job_data = status_resp.json()
        assert job_data["job_id"] == job_id
        assert job_data["status"] in ["pending", "processing", "completed"]


@pytest.mark.asyncio
async def test_ingest_unsupported_file_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {
            "file": (
                "bad_file.xyz",
                io.BytesIO(b"bad content"),
                "application/octet-stream",
            )
        }
        response = await client.post("/ingest", files=files)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ingest_rejects_file_over_configured_size(monkeypatch):
    monkeypatch.setattr(
        routes_ingest,
        "get_settings",
        lambda: SimpleNamespace(MAX_UPLOAD_SIZE_BYTES=8),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("too_large.txt", io.BytesIO(b"123456789"), "text/plain")}
        response = await client.post("/ingest", files=files)

    assert response.status_code == 413
    assert "maximum upload size of 8 bytes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/ingest/documents/non_existent_doc_id")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
