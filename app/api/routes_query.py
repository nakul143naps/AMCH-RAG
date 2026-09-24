import time

from fastapi import APIRouter, HTTPException, status

from app.observability import REQUEST_LATENCY_SECONDS
from app.retrieval.models import QueryRequest, QueryResponse
from app.retrieval.service import BaselineRAGService

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question against the knowledge base",
    description="Non-streaming baseline RAG endpoint executing hybrid retrieval and grounded generation with verifiable citations.",
)
async def query_knowledge_base(request: QueryRequest) -> QueryResponse:
    """Execute query retrieval and grounded answer synthesis."""
    start_time = time.perf_counter()
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
