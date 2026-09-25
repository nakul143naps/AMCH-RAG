"""Cache manager supporting Redis and zero-dependency local SQLite fallback."""

import json
import os
import sqlite3
import time
from typing import Any, Optional

import redis

from app.config import get_settings


class SQLiteCache:
    """Zero-dependency local disk SQLite cache with TTL support."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10.0)

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doc_cache_index (
                    doc_id TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    PRIMARY KEY (doc_id, cache_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_summaries (
                    doc_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    topics TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, key: str) -> str | None:
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            if row:
                value, expires_at = row
                if expires_at > now:
                    return value
                # Expired
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
        return None

    def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int = 86400,
        doc_ids: list[str] | None = None,
    ) -> None:
        expires_at = time.time() + ttl_seconds
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries (key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at),
            )
            if doc_ids:
                for doc_id in doc_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO doc_cache_index (doc_id, cache_key) VALUES (?, ?)",
                        (doc_id, key),
                    )
            conn.commit()

    def invalidate_by_doc(self, doc_id: str) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT cache_key FROM doc_cache_index WHERE doc_id = ?",
                (doc_id,),
            )
            keys = [row[0] for row in cursor.fetchall()]
            if keys:
                conn.executemany(
                    "DELETE FROM cache_entries WHERE key = ?", [(k,) for k in keys]
                )
                conn.execute("DELETE FROM doc_cache_index WHERE doc_id = ?", (doc_id,))
                conn.commit()
            return len(keys)
        return 0

    def clear(self) -> None:
        """Clear all cache entries from SQLite."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cache_entries")
            conn.execute("DELETE FROM doc_cache_index")
            conn.commit()

    def set_document_summary(
        self,
        doc_id: str,
        source_name: str,
        summary: str,
        topics: str,
    ) -> None:
        """Store or update a comprehensive high-level document summary."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO document_summaries (doc_id, source_name, summary, topics, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_id, source_name, summary, topics, time.time()),
            )
            conn.commit()

    def get_document_summary(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve stored high-level summary for a specific document."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT doc_id, source_name, summary, topics, updated_at FROM document_summaries WHERE doc_id = ?",
                (doc_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "doc_id": row[0],
                    "source_name": row[1],
                    "summary": row[2],
                    "topics": row[3],
                    "updated_at": row[4],
                }
            return None

    def get_all_document_summaries(self) -> list[dict[str, Any]]:
        """Retrieve all high-level document summaries sorted by updated_at descending."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT doc_id, source_name, summary, topics, updated_at FROM document_summaries ORDER BY updated_at DESC"
            )
            rows = cursor.fetchall()
            return [
                {
                    "doc_id": r[0],
                    "source_name": r[1],
                    "summary": r[2],
                    "topics": r[3],
                    "updated_at": r[4],
                }
                for r in rows
            ]


class CacheManager:
    """Unified cache manager switching between Redis and SQLite."""

    _instance: Optional["CacheManager"] = None

    @classmethod
    def get_instance(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = CacheManager()
        return cls._instance

    def __init__(self) -> None:
        settings = get_settings()
        self.redis_client: redis.Redis | None = None
        self.sqlite_cache: SQLiteCache = SQLiteCache(settings.LOCAL_CACHE_PATH)

        if settings.REDIS_URL:
            try:
                client = redis.Redis.from_url(
                    settings.REDIS_URL, decode_responses=True, socket_timeout=2.0
                )
                client.ping()
                self.redis_client = client
            except Exception:  # noqa: BLE001
                self.redis_client = None

    def check_health(self) -> dict[str, Any]:
        """Check cache backend status."""
        if self.redis_client is not None:
            try:
                self.redis_client.ping()
                return {"backend": "redis", "status": "ok"}
            except Exception as e:  # noqa: BLE001
                return {
                    "backend": "redis",
                    "status": "unreachable",
                    "fallback": "sqlite",
                    "error": str(e),
                }
        return {
            "backend": "sqlite",
            "status": "ok",
            "path": get_settings().LOCAL_CACHE_PATH,
        }

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve and parse JSON value from cache."""
        if self.redis_client is not None:
            try:
                val = self.redis_client.get(key)
                if val:
                    return json.loads(val)
            except Exception:  # noqa: BLE001, S110
                pass
        val_str = self.sqlite_cache.get(key)
        if val_str:
            return json.loads(val_str)
        return None

    def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl_seconds: int = 86400,
        doc_ids: list[str] | None = None,
    ) -> None:
        """Store JSON value in cache."""
        serialized = json.dumps(value)
        if self.redis_client is not None:
            try:
                self.redis_client.setex(key, ttl_seconds, serialized)
                if doc_ids:
                    for doc_id in doc_ids:
                        self.redis_client.sadd(f"doc_index:{doc_id}", key)
            except Exception:  # noqa: BLE001, S110
                pass
        self.sqlite_cache.set(key, serialized, ttl_seconds, doc_ids)

    def invalidate_by_doc(self, doc_id: str) -> int:
        """Invalidate all cache entries associated with a document ID."""
        count = 0
        if self.redis_client is not None:
            try:
                keys = self.redis_client.smembers(f"doc_index:{doc_id}")
                if keys:
                    self.redis_client.delete(*keys)
                    self.redis_client.delete(f"doc_index:{doc_id}")
                    count += len(keys)
            except Exception:  # noqa: BLE001, S110
                pass
        count += self.sqlite_cache.invalidate_by_doc(doc_id)
        return count

    def clear(self) -> None:
        """Clear all cache entries across active backends."""
        if self.redis_client is not None:
            try:
                self.redis_client.flushdb()
            except Exception:  # noqa: BLE001, S110
                pass
        self.sqlite_cache.clear()

    def set_document_summary(
        self,
        doc_id: str,
        source_name: str,
        summary: str,
        topics: str,
    ) -> None:
        """Store or update a high-level document summary."""
        self.sqlite_cache.set_document_summary(doc_id, source_name, summary, topics)

    def get_document_summary(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve stored high-level summary for a specific document."""
        return self.sqlite_cache.get_document_summary(doc_id)

    def get_all_document_summaries(self) -> list[dict[str, Any]]:
        """Retrieve all high-level document summaries."""
        return self.sqlite_cache.get_all_document_summaries()
