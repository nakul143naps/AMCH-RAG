"""Embedding engine providing local dense (BGE) and sparse (BM25) vector generation."""

import os
from dataclasses import dataclass
from typing import Optional

from fastembed import SparseTextEmbedding, TextEmbedding

# Suppress HuggingFace Windows symlink warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from app.config import get_settings


@dataclass
class SparseVectorData:
    """Container for sparse vector indices and values."""

    indices: list[int]
    values: list[float]


class EmbeddingEngine:
    """Manages dense and sparse embedding models using FastEmbed."""

    _instance: Optional["EmbeddingEngine"] = None

    @classmethod
    def get_instance(cls) -> "EmbeddingEngine":
        """Return singleton instance of EmbeddingEngine."""
        if cls._instance is None:
            cls._instance = EmbeddingEngine()
        return cls._instance

    def __init__(self) -> None:
        """Initialize dense and sparse embedding models."""
        settings = get_settings()
        self.dense_model_name = settings.EMBEDDING_MODEL
        self.sparse_model_name = "Qdrant/bm25"

        self._dense_model: TextEmbedding | None = None
        self._sparse_model: SparseTextEmbedding | None = None

    @property
    def dense_model(self) -> TextEmbedding:
        """Lazy-load dense model."""
        if self._dense_model is None:
            self._dense_model = TextEmbedding(model_name=self.dense_model_name)
        return self._dense_model

    @property
    def sparse_model(self) -> SparseTextEmbedding:
        """Lazy-load sparse model."""
        if self._sparse_model is None:
            self._sparse_model = SparseTextEmbedding(model_name=self.sparse_model_name)
        return self._sparse_model

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for a batch of strings."""
        if not texts:
            return []
        embeddings = list(self.dense_model.embed(texts))
        return [e.tolist() for e in embeddings]

    def embed_sparse(self, texts: list[str]) -> list[SparseVectorData]:
        """Generate sparse BM25 embeddings for a batch of strings."""
        if not texts:
            return []
        embeddings = list(self.sparse_model.embed(texts))
        results = []
        for e in embeddings:
            results.append(
                SparseVectorData(
                    indices=e.indices.tolist(),
                    values=e.values.tolist(),
                )
            )
        return results

    def embed_query_dense(self, query: str) -> list[float]:
        """Generate a single dense embedding for a query string."""
        results = self.embed_dense([query])
        return results[0]

    def embed_query_sparse(self, query: str) -> SparseVectorData:
        """Generate a single sparse embedding for a query string."""
        results = self.embed_sparse([query])
        return results[0]
