"""Tests for POST /query Server-Sent Events (SSE) streaming and event emission."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.state import create_initial_state
from app.main import app
from app.retrieval.models import Citation


@pytest.mark.asyncio
async def test_query_streaming_sse_tokens_and_done():
    """Verify that POST /query with stream=True emits token and done SSE events."""
    mock_state = create_initial_state(query="Explain AMCH-RAG architecture")
    mock_state["final_answer"] = "AMCH-RAG combines hybrid retrieval with agentic self-correction."
    mock_state["citations"] = [
        Citation(
            index=1,
            source="design.md",
            doc_id="doc_123",
            chunk_id="chunk_456",
            section="Architecture",
            snippet="AMCH-RAG combines hybrid retrieval",
        )
    ]
    mock_state["correction_attempts"] = 1

    transport = ASGITransport(app=app)
    with patch("app.api.routes_query.AgentService.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_state

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                json={
                    "query": "Explain AMCH-RAG architecture",
                    "stream": True,
                },
                headers={"Accept": "text/event-stream"},
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Parse SSE lines
            events = []
            for line in response.text.split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(payload)

            event_types = [e["type"] for e in events]
            assert "correction" in event_types
            assert "citation" in event_types
            assert "token" in event_types
            assert "done" in event_types

            # Verify citation structure
            cit_events = [e for e in events if e["type"] == "citation"]
            assert len(cit_events) == 1
            assert cit_events[0]["source"] == "design.md"
            assert cit_events[0]["chunk_id"] == "chunk_456"

            # Verify tokens reconstruct original answer
            token_events = [e for e in events if e["type"] == "token"]
            reconstructed = "".join(e["content"] for e in token_events).strip()
            assert "AMCH-RAG combines hybrid retrieval" in reconstructed

            # Verify done event has trace_id
            done_event = next(e for e in events if e["type"] == "done")
            assert "trace_id" in done_event
            assert len(done_event["trace_id"]) > 0


@pytest.mark.asyncio
async def test_query_non_streaming_fallback_retained():
    """Verify that POST /query with stream=False retains standard JSON QueryResponse."""
    transport = ASGITransport(app=app)
    with patch("app.retrieval.service.BaselineRAGService.answer", new_callable=AsyncMock) as mock_answer:
        from app.retrieval.models import QueryResponse

        mock_answer.return_value = QueryResponse(
            answer="Non-streaming response test.",
            citations=[],
            provider_used="gemini",
            trace_id="trace-test-non-stream",
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/query",
                json={"query": "Test non-streaming query", "stream": False},
                headers={"Accept": "application/json"},
            )
            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type", "")
            data = response.json()
            assert data["answer"] == "Non-streaming response test."
            assert data["provider_used"] == "gemini"
