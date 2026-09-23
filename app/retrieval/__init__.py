"""Retrieval subpackage providing hybrid search, vector storage, and local embeddings."""

from app.retrieval.embeddings import EmbeddingEngine, SparseVectorData
from app.retrieval.models import RetrievalQuery, RetrievedChunk
from app.retrieval.retriever import HybridRetriever
from app.retrieval.vector_store import VectorStoreManager

__all__ = [
    "EmbeddingEngine",
    "HybridRetriever",
    "RetrievalQuery",
    "RetrievedChunk",
    "SparseVectorData",
    "VectorStoreManager",
]
