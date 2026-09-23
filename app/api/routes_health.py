"""Health and status check routes."""

from fastapi import APIRouter

from app.cache.manager import CacheManager
from app.gateway.client import ModelGateway
from app.retrieval.vector_store import VectorStoreManager

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """Return live status of Qdrant, Cache, and configured LLM providers."""
    vector_mgr = VectorStoreManager.get_instance()
    cache_mgr = CacheManager.get_instance()
    gateway = ModelGateway.get_instance()

    qdrant_healthy = vector_mgr.check_health()
    cache_health = cache_mgr.check_health()
    providers_status = gateway.get_configured_providers()

    overall_status = "ok" if qdrant_healthy else "degraded"

    return {
        "status": overall_status,
        "qdrant": qdrant_healthy,
        "cache": cache_health,
        "providers": providers_status,
    }
