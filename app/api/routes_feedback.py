"""FastAPI router for user feedback capture linked to trace_id."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, status

from app.api.models import FeedbackRequest, FeedbackResponse
from app.observability import record_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])

# In-memory feedback store (also persisted to logs and metrics)
FEEDBACK_STORE: list[dict[str, Any]] = []


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit user feedback on a generated answer",
    description="Captures thumbs-up or thumbs-down feedback linked to a query trace_id.",
)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Record user rating and comment for a specific query execution trace."""
    feedback_id = f"fb_{uuid.uuid4().hex[:10]}"
    record = {
        "feedback_id": feedback_id,
        "trace_id": request.trace_id,
        "rating": request.rating,
        "comment": request.comment,
    }
    FEEDBACK_STORE.append(record)
    record_feedback(rating=request.rating)

    logger.info(
        "Captured user feedback: id=%s trace_id=%s rating=%s comment='%s'",
        feedback_id,
        request.trace_id,
        request.rating,
        request.comment or "",
    )

    return FeedbackResponse(
        status="received",
        feedback_id=feedback_id,
        trace_id=request.trace_id,
        rating=request.rating,
    )


def get_all_feedback() -> list[dict[str, Any]]:
    """Helper returning all recorded feedback."""
    return list(FEEDBACK_STORE)
