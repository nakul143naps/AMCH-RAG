"""Retrieval subpackage providing hybrid search, vector storage, and local embeddings."""

from app.retrieval.embeddings import EmbeddingEngine, SparseVectorData
from app.retrieval.models import (
    Citation,
    QueryRequest,
    QueryResponse,
    RetrievalQuery,
    RetrievedChunk,
)
from app.retrieval.reranker import RerankerService
from app.retrieval.retriever import HybridRetriever
from app.retrieval.service import BaselineRAGService
from app.retrieval.vector_store import VectorStoreManager

__all__ = [
    "BaselineRAGService",
    "Citation",
    "EmbeddingEngine",
    "HybridRetriever",
    "QueryRequest",
    "QueryResponse",
    "RerankerService",
    "RetrievalQuery",
    "RetrievedChunk",
    "SparseVectorData",
    "VectorStoreManager",
]
