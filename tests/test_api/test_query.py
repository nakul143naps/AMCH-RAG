"""Tests for POST /query endpoint and BaselineRAGService."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import QdrantClient

from app.ingestion.pipeline import IngestionPipeline
from app.main import app
from app.retrieval.vector_store import VectorStoreManager


@pytest.fixture
def populated_vector_store(tmp_path: Path):
    """Set up an in-memory Qdrant store with sample documents for query testing."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)

    # Ingest a public document
    doc1 = tmp_path / "cardiology_guide.md"
    doc1.write_text(
        "# Cardiology Protocol\n"
        "Myocardial infarction occurs when coronary blood flow is blocked, leading to severe chest pain.",
        encoding="utf-8",
    )
    pipeline.process_file(
        file_path=doc1,
        source_name="cardiology_guide.md",
        access_level="public",
    )

    # Ingest a confidential document
    doc2 = tmp_path / "classified_telemetry.txt"
    doc2.write_text(
        "Top-secret telemetry error: CLASSIFIED-ERR-7788 detected in orbit subsystem.",
        encoding="utf-8",
    )
    pipeline.process_file(
        file_path=doc2,
        source_name="classified_telemetry.txt",
        access_level="confidential",
    )

    return vector_mgr


@pytest.mark.asyncio
async def test_query_success_with_citations(populated_vector_store):
    """Verify that POST /query retrieves relevant context, invokes gateway, and returns citations."""
    mock_generate = AsyncMock(
        return_value=(
            "Myocardial infarction is caused by blocked coronary blood flow [1].",
            "gemini",
        )
    )

    with patch("app.retrieval.service.ModelGateway.generate", mock_generate):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                json={
                    "query": "What causes myocardial infarction?",
                    "limit": 3,
                    "access_level": "public",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "Myocardial infarction is caused" in data["answer"]
    assert data["provider_used"] == "gemini"
    assert data["trace_id"] is not None
    assert len(data["citations"]) > 0

    first_cit = data["citations"][0]
    assert first_cit["index"] == 1
    assert first_cit["source"] == "cardiology_guide.md"
    assert "blocked" in first_cit["snippet"]


@pytest.mark.asyncio
async def test_query_empty_knowledge_base():
    """Verify response when vector store has no relevant chunks."""
    # Isolated empty client
    test_client = QdrantClient(":memory:")
    VectorStoreManager.get_instance(client=test_client).ensure_collections()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/query",
            json={
                "query": "Completely unknown subject XYZ",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "could not find any relevant information" in data["answer"]
    assert len(data["citations"]) == 0
    assert data["provider_used"] == "none"


@pytest.mark.asyncio
async def test_query_access_level_isolation(populated_vector_store):
    """Verify that a user without confidential access cannot retrieve confidential citations."""
    mock_generate = AsyncMock(
        return_value=(
            "No classified info found.",
            "gemini",
        )
    )

    with patch("app.retrieval.service.ModelGateway.generate", mock_generate):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Querying as public for confidential error
            response = await client.post(
                "/query",
                json={
                    "query": "CLASSIFIED-ERR-7788",
                    "access_level": "public",
                },
            )

    assert response.status_code == 200
    data = response.json()
    # Classified telemetry document should NOT be in citations
    for cit in data["citations"]:
        assert cit["source"] != "classified_telemetry.txt"


@pytest.mark.asyncio
async def test_query_provider_failure_handling(populated_vector_store):
    """Verify that provider failure raises 503 Service Unavailable."""
    mock_generate = AsyncMock(
        side_effect=RuntimeError("All configured providers failed")
    )

    with patch("app.retrieval.service.ModelGateway.generate", mock_generate):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                json={
                    "query": "What causes myocardial infarction?",
                    "access_level": "public",
                },
            )

    assert response.status_code == 503
    assert "Model generation failed" in response.json()["detail"]
