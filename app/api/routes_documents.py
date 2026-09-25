"""FastAPI router for document catalog inspection and deletion with cache invalidation."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.models import DocumentDeleteResponse, DocumentItem, DocumentListResponse
from app.cache.service import TwoTierCacheService
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all ingested documents",
    description="Returns distinct ingested documents along with chunk count, access level, and ingestion timestamp.",
)
async def list_documents() -> DocumentListResponse:
    """Retrieve all unique ingested documents from the vector database."""
    vector_mgr = VectorStoreManager.get_instance()
    raw_docs = vector_mgr.list_documents()

    items = [
        DocumentItem(
            doc_id=d["doc_id"],
            source_name=d["source_name"],
            source_type=d["source_type"],
            access_level=d["access_level"],
            chunk_count=d["chunk_count"],
            version=d.get("version", 1),
            created_at=d.get("created_at"),
            summary=d.get("summary"),
        )
        for d in raw_docs
    ]

    return DocumentListResponse(documents=items, total=len(items))


@router.delete(
    "/{doc_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an ingested document and invalidate caches",
    description="Deletes all chunks belonging to doc_id from Qdrant and purges associated entries from exact and semantic caches.",
)
async def delete_document(doc_id: str) -> DocumentDeleteResponse:
    """Remove a document from vector storage and invalidate associated cache entries."""
    vector_mgr = VectorStoreManager.get_instance()
    cache_service = TwoTierCacheService.get_instance()

    try:
        # Delete from Qdrant knowledge_base collection
        vector_mgr.delete_by_doc_id(doc_id=doc_id)

        # Invalidate exact and semantic cache entries citing this document
        invalidated_count = cache_service.invalidate_by_doc(doc_id=doc_id)

        logger.info(
            "Deleted document '%s' from Qdrant; evicted %d linked cache entries",
            doc_id,
            invalidated_count,
        )

        return DocumentDeleteResponse(
            doc_id=doc_id,
            status="deleted",
            cache_invalidated=True,
        )
    except Exception as e:
        logger.error("Failed to delete document '%s': %s", doc_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {e}",
        ) from e


@router.post(
    "/cache/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear all exact and semantic caches",
)
async def clear_cache() -> dict[str, str]:
    """Purge all entries from exact SQLite/Redis cache and Qdrant semantic cache."""
    cache_service = TwoTierCacheService.get_instance()
    cache_service.clear()
    logger.info("Cleared all exact and semantic caches via API")
    return {"status": "success", "message": "All caches successfully cleared"}

