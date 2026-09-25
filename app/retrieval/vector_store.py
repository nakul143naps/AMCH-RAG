"""Vector store management for AMCH-RAG using Qdrant (local embedded or remote server)."""

import os
import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchValue,
    PointStruct,
    Prefetch,
    ScoredPoint,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.config import get_settings
from app.ingestion.models import ChunkPayload
from app.retrieval.embeddings import SparseVectorData


class VectorStoreManager:
    """Manages Qdrant client connection, collections, and vector upsert operations."""

    _instance: Optional["VectorStoreManager"] = None
    _client: QdrantClient | None = None

    @classmethod
    def get_instance(cls, client: QdrantClient | None = None) -> "VectorStoreManager":
        """Return singleton instance of VectorStoreManager, optionally injecting client."""
        if cls._instance is None:
            cls._instance = VectorStoreManager(client=client)
        elif client is not None:
            cls._instance._client = client
        return cls._instance

    def __init__(self, client: QdrantClient | None = None) -> None:
        """Initialize the Qdrant client based on settings or injected client."""
        if client is not None:
            self._client = client
            return

        settings = get_settings()
        if settings.QDRANT_URL:
            self._client = QdrantClient(url=settings.QDRANT_URL)
        else:
            os.makedirs(settings.QDRANT_PATH, exist_ok=True)
            self._client = QdrantClient(path=settings.QDRANT_PATH)

    @property
    def client(self) -> QdrantClient:
        """Get the active Qdrant client."""
        if self._client is None:
            raise RuntimeError("QdrantClient is not initialized.")
        return self._client

    def ensure_collections(self) -> None:
        """Ensure the knowledge base and semantic cache collections exist with dense and sparse vectors."""
        settings = get_settings()
        collections = [c.name for c in self.client.get_collections().collections]

        # 1. Main Knowledge Base Collection
        if settings.QDRANT_COLLECTION not in collections:
            self.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config={
                    "dense": VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
                },
            )

        # 2. Semantic Cache Collection
        if settings.QDRANT_SEMANTIC_CACHE_COLLECTION not in collections:
            self.client.create_collection(
                collection_name=settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                vectors_config={
                    "dense": VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    )
                },
            )

        # 3. User Memory Collection (Long-Term durable facts)
        if settings.QDRANT_USER_MEMORY_COLLECTION not in collections:
            self.client.create_collection(
                collection_name=settings.QDRANT_USER_MEMORY_COLLECTION,
                vectors_config={
                    "dense": VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
                },
            )

    def upsert_chunks(
        self,
        chunks: list[ChunkPayload],
        dense_vectors: list[list[float]],
        sparse_vectors: list[SparseVectorData] | None = None,
        collection_name: str | None = None,
    ) -> int:
        """Upsert chunk payloads and vectors into Qdrant."""
        if not chunks:
            return 0

        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION
        self.ensure_collections()

        points: list[PointStruct] = []
        for i, chunk in enumerate(chunks):
            # Deterministic UUID based on doc_id and chunk_index
            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.doc_id}_{chunk.chunk_index}")
            )

            vector_dict: dict = {"dense": dense_vectors[i]}
            if sparse_vectors and i < len(sparse_vectors):
                sp = sparse_vectors[i]
                vector_dict["sparse"] = SparseVector(
                    indices=sp.indices,
                    values=sp.values,
                )

            # Dump payload with JSON-serializable types
            payload = chunk.model_dump(mode="json")

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector_dict,
                    payload=payload,
                )
            )

        self.client.upsert(collection_name=col, points=points)
        return len(points)

    def get_chunks_by_doc_id(
        self, doc_id: str, collection_name: str | None = None
    ) -> list[ChunkPayload]:
        """Retrieve all stored chunks for a specific document ID."""
        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION

        results, _ = self.client.scroll(
            collection_name=col,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=1000,
            with_payload=True,
        )

        chunks: list[ChunkPayload] = []
        for res in results:
            if res.payload:
                chunks.append(ChunkPayload.model_validate(res.payload))

        # Sort by chunk_index
        chunks.sort(key=lambda x: x.chunk_index)
        return chunks

    def delete_by_doc_id(self, doc_id: str, collection_name: str | None = None) -> None:
        """Delete all chunks belonging to a specific document."""
        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION

        self.client.delete(
            collection_name=col,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            ),
        )

    def count_chunks(self, collection_name: str | None = None) -> int:
        """Count total chunk points in the collection."""
        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION
        try:
            return self.client.count(collection_name=col).count
        except Exception:  # noqa: BLE001
            return 0

    def check_health(self) -> bool:
        """Check if Qdrant is reachable and responding."""
        try:
            self.client.get_collections()
            return True
        except Exception:  # noqa: BLE001
            return False

    def query_hybrid(
        self,
        dense_vector: list[float] | None = None,
        sparse_vector: SparseVectorData | None = None,
        limit: int = 10,
        prefetch_limit: int = 40,
        query_filter: Filter | None = None,
        collection_name: str | None = None,
    ) -> list[ScoredPoint]:
        """Execute hybrid search using dense and sparse prefetch with RRF fusion, or single-mode fallback."""
        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION
        self.ensure_collections()

        has_dense = dense_vector is not None and len(dense_vector) > 0
        has_sparse = sparse_vector is not None and len(sparse_vector.indices) > 0

        if has_dense and has_sparse:
            prefetch = [
                Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=prefetch_limit,
                ),
                Prefetch(
                    query=SparseVector(
                        indices=sparse_vector.indices,
                        values=sparse_vector.values,
                    ),
                    using="sparse",
                    limit=prefetch_limit,
                ),
            ]
            response = self.client.query_points(
                collection_name=col,
                prefetch=prefetch,
                query=FusionQuery(fusion=Fusion.RRF),
                query_filter=query_filter,
                limit=limit,
            )
            return response.points

        if has_dense:
            response = self.client.query_points(
                collection_name=col,
                query=dense_vector,
                using="dense",
                query_filter=query_filter,
                limit=limit,
            )
            return response.points

        if has_sparse:
            response = self.client.query_points(
                collection_name=col,
                query=SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                ),
                using="sparse",
                query_filter=query_filter,
                limit=limit,
            )
            return response.points

        return []

    def list_documents(self, collection_name: str | None = None) -> list[dict[str, Any]]:
        """List distinct ingested documents with metadata and chunk counts."""
        settings = get_settings()
        col = collection_name or settings.QDRANT_COLLECTION
        try:
            points, _ = self.client.scroll(
                collection_name=col,
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:  # noqa: BLE001
            return []

        docs_map: dict[str, dict[str, Any]] = {}
        snippets_map: dict[str, list[str]] = {}
        for pt in points:
            if not pt.payload:
                continue
            doc_id = pt.payload.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in docs_map:
                docs_map[doc_id] = {
                    "doc_id": doc_id,
                    "source_name": pt.payload.get("source", doc_id),
                    "source_type": pt.payload.get("source_type", "unknown"),
                    "access_level": pt.payload.get("access_level", "default"),
                    "version": pt.payload.get("version", 1),
                    "chunk_count": 0,
                    "created_at": pt.payload.get("created_at"),
                    "summary": "",
                }
                snippets_map[doc_id] = []
            docs_map[doc_id]["chunk_count"] += 1

            content = (pt.payload.get("content") or "").strip()
            if content and len(snippets_map[doc_id]) < 4:
                first_words = " ".join(content.split()[:25])
                if first_words not in snippets_map[doc_id]:
                    snippets_map[doc_id].append(first_words)

        for doc_id, doc_info in docs_map.items():
            if snippets_map.get(doc_id):
                doc_info["summary"] = " | ".join(snippets_map[doc_id])

        return list(docs_map.values())

