"""Query API routes for baseline RAG and agentic Server-Sent Events (SSE) streaming."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.agent.service import AgentService
from app.observability import REQUEST_LATENCY_SECONDS
from app.retrieval.models import QueryRequest
from app.retrieval.service import BaselineRAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


async def sse_event_stream(
    request: QueryRequest, trace_id: str, start_time: float
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events (SSE) for agentic RAG query execution.

    Emits structured events conforming to DESIGN.md §5:
    - { "type": "correction", "reason": str } (if query rewrite or groundedness retry occurred)
    - { "type": "citation", "index": int, "source": str, "chunk_id": str }
    - { "type": "token", "content": str }
    - { "type": "done", "trace_id": str }
    """
    try:
        agent_service = AgentService()
        final_state = await agent_service.ainvoke(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id,
            access_level=request.access_level,
            trace_id=trace_id,
        )

        # 1. Emit correction events if CRAG or Groundedness retries were triggered
        if final_state.get("correction_attempts", 0) > 0:
            yield f"data: {json.dumps({'type': 'correction', 'reason': 'Query rewritten to optimize retrieval recall'})}\n\n"
        if final_state.get("groundedness_retries", 0) > 0:
            yield f"data: {json.dumps({'type': 'correction', 'reason': 'Draft answer regenerated to ensure factual groundedness'})}\n\n"

        # 2. Emit structured citation events
        citations = final_state.get("citations", [])
        for c in citations:
            c_dict = c if isinstance(c, dict) else c.model_dump()
            yield f"data: {json.dumps({'type': 'citation', 'index': c_dict.get('index'), 'source': c_dict.get('source'), 'chunk_id': c_dict.get('chunk_id')})}\n\n"

        # 3. Stream synthesized tokens
        final_answer = final_state.get("final_answer") or ""
        words = final_answer.split(" ")
        for i, word in enumerate(words):
            token_content = word + (" " if i < len(words) - 1 else "")
            yield f"data: {json.dumps({'type': 'token', 'content': token_content})}\n\n"
            await asyncio.sleep(0.01)

        # 4. Emit terminal completion event
        effective_trace_id = final_state.get("trace_id", trace_id)
        yield f"data: {json.dumps({'type': 'done', 'trace_id': effective_trace_id})}\n\n"

        # Record total duration into Prometheus
        duration = time.perf_counter() - start_time
        REQUEST_LATENCY_SECONDS.labels(endpoint="/query").observe(duration)

        # Post-generation background fact extraction for durable user memory
        if request.user_id and final_answer:
            try:
                from app.memory.long_term import UserMemoryService

                user_mem = UserMemoryService.get_instance()
                extracted = await user_mem.extract_facts(
                    user_message=request.query,
                    assistant_response=final_answer,
                )
                if extracted:
                    await user_mem.async_store_facts(
                        user_id=request.user_id, facts=extracted
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("Post-stream fact extraction failed: %s", e)

    except Exception as e:  # noqa: BLE001
        logger.error("SSE stream error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Ask a question against the knowledge base",
    description="Query endpoint supporting non-streaming JSON responses and Server-Sent Events (SSE) streaming.",
)
async def query_knowledge_base(
    request: QueryRequest,
    req: Request,
) -> Any:
    """Execute query retrieval and grounded answer synthesis (JSON or SSE stream)."""
    start_time = time.perf_counter()
    accept_header = req.headers.get("accept", "")
    wants_stream = request.stream or "text/event-stream" in accept_header

    trace_id = str(uuid.uuid4())

    if wants_stream:
        return StreamingResponse(
            sse_event_stream(request, trace_id, start_time),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Trace-ID": trace_id,
            },
        )

    # Standard non-streaming JSON path
    try:
        service = BaselineRAGService()
        response = await service.answer(request)
        duration = time.perf_counter() - start_time
        REQUEST_LATENCY_SECONDS.labels(endpoint="/query").observe(duration)
        return response
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model generation failed: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {e}",
        ) from e
