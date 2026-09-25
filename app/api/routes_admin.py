"""FastAPI router for Mr. Admin monitoring and control operations."""

import json
import logging
import sqlite3
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.cache.manager import CacheManager
from app.config import get_settings
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin-api", tags=["Admin Operations"])

# In-memory dynamic guardrails state
_GUARDRAILS_CONFIG = {
    "groundedness_threshold": 1.0,
    "strict_grounding": True,
    "crag_fallback_enabled": True,
    "max_correction_retries": 2,
    "confidence_gate": 0.50,
    "prompt_injection_shield": True,
}


class MemoryFactCreate(BaseModel):
    user_id: str = "default_user"
    fact: str
    category: str = "preference"


class GuardrailsUpdate(BaseModel):
    groundedness_threshold: float | None = None
    strict_grounding: bool | None = None
    crag_fallback_enabled: bool | None = None
    max_correction_retries: int | None = None
    confidence_gate: float | None = None
    prompt_injection_shield: bool | None = None


@router.get("/cache")
async def get_all_cache_entries() -> dict[str, Any]:
    """Retrieve all exact L1 cache items and L2 semantic cache vectors."""
    settings = get_settings()
    sqlite_entries: list[dict[str, Any]] = []

    # 1. Fetch SQLite L1 entries
    db_path = settings.LOCAL_CACHE_PATH
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, expires_at FROM cache_entries ORDER BY expires_at DESC LIMIT 100")
        rows = cursor.fetchall()
        now = time.time()

        for key, val_str, expires_at in rows:
            query = "Unknown query"
            answer_preview = ""
            try:
                parsed = json.loads(val_str)
                if isinstance(parsed, dict):
                    query = parsed.get("query", key)
                    ans = parsed.get("answer", "")
                    answer_preview = ans[:160] + ("..." if len(ans) > 160 else "")
                else:
                    answer_preview = str(val_str)[:160]
            except Exception:
                answer_preview = str(val_str)[:160]

            sqlite_entries.append({
                "key": key,
                "query": query,
                "preview": answer_preview,
                "expires_at": expires_at,
                "is_expired": expires_at < now,
            })
        conn.close()
    except Exception as e:
        logger.warning("Could not read SQLite cache for admin: %s", e)

    # 2. Fetch Qdrant L2 semantic cache points
    semantic_entries: list[dict[str, Any]] = []
    try:
        vector_mgr = VectorStoreManager.get_instance()
        client = vector_mgr.client
        points, _ = client.scroll(
            collection_name=settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
            limit=50,
            with_payload=True,
        )
        for pt in points:
            payload = pt.payload or {}
            semantic_entries.append({
                "id": str(pt.id),
                "query": payload.get("query", "Unknown semantic query"),
                "access_level": payload.get("access_level", "default"),
                "doc_ids": payload.get("doc_ids", []),
                "exact_key": payload.get("exact_key", ""),
            })
    except Exception as e:
        logger.warning("Could not scroll semantic cache for admin: %s", e)

    return {
        "l1_sqlite": {
            "path": db_path,
            "total_count": len(sqlite_entries),
            "entries": sqlite_entries,
        },
        "l2_semantic": {
            "collection": settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
            "total_count": len(semantic_entries),
            "entries": semantic_entries,
        },
    }


@router.delete("/cache/entry")
async def delete_cache_entry(
    key: str | None = Query(None, description="SQLite cache key"),
    point_id: str | None = Query(None, description="Qdrant point ID"),
) -> dict[str, str]:
    """Delete a specific cache item from L1 SQLite or L2 Qdrant."""
    settings = get_settings()

    if key:
        try:
            conn = sqlite3.connect(settings.LOCAL_CACHE_PATH, timeout=5.0)
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    if point_id:
        try:
            vector_mgr = VectorStoreManager.get_instance()
            vector_mgr.client.delete(
                collection_name=settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                points_selector=[point_id],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return {"status": "deleted"}


@router.get("/memory")
async def get_all_user_memories() -> dict[str, Any]:
    """Retrieve all user memory points from Qdrant user_memory collection."""
    settings = get_settings()
    memories: list[dict[str, Any]] = []

    try:
        vector_mgr = VectorStoreManager.get_instance()
        points, _ = vector_mgr.client.scroll(
            collection_name=settings.QDRANT_USER_MEMORY_COLLECTION,
            limit=50,
            with_payload=True,
        )
        for pt in points:
            payload = pt.payload or {}
            memories.append({
                "id": str(pt.id),
                "user_id": payload.get("user_id", "default_user"),
                "fact": payload.get("fact", "No fact text"),
                "category": payload.get("category", "preference"),
                "created_at": payload.get("created_at", ""),
            })
    except Exception as e:
        logger.warning("Could not scroll user_memory: %s", e)

    return {
        "collection": settings.QDRANT_USER_MEMORY_COLLECTION,
        "total": len(memories),
        "facts": memories,
    }


@router.post("/memory")
async def add_user_memory(item: MemoryFactCreate) -> dict[str, Any]:
    """Add a new user memory fact into Qdrant."""
    from app.memory.long_term import UserMemoryService

    try:
        service = UserMemoryService.get_instance()
        await service.async_store_facts(
            user_id=item.user_id,
            facts=[{"fact": item.fact, "category": item.category}],
        )
        return {"status": "created", "fact": item.fact}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/memory/{point_id}")
async def delete_user_memory(point_id: str) -> dict[str, str]:
    """Delete a user memory point from Qdrant."""
    settings = get_settings()
    try:
        vector_mgr = VectorStoreManager.get_instance()
        vector_mgr.client.delete(
            collection_name=settings.QDRANT_USER_MEMORY_COLLECTION,
            points_selector=[point_id],
        )
        return {"status": "deleted", "id": point_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/guardrails")
async def get_guardrails_config() -> dict[str, Any]:
    """Get active hallucination and safety guardrail settings."""
    return _GUARDRAILS_CONFIG


@router.post("/guardrails")
async def update_guardrails_config(updates: GuardrailsUpdate) -> dict[str, Any]:
    """Update active guardrail parameters."""
    for field, val in updates.model_dump(exclude_unset=True).items():
        if val is not None:
            _GUARDRAILS_CONFIG[field] = val
    return {"status": "updated", "config": _GUARDRAILS_CONFIG}
