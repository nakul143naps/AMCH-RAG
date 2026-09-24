"""FastAPI router for Prometheus metrics exposition."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.observability.metrics import get_metrics_exposition

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def get_metrics() -> Response:
    """Expose application metrics in standard Prometheus exposition format."""
    content = get_metrics_exposition()
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)
