"""Configuration management for AMCH-RAG using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application & Environment
    PROJECT_NAME: str = "AMCH-RAG"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Primary Provider: Google Gemini (Gemini AI Pro umbrella)
    GEMINI_API_KEY: str = Field(
        default="", description="Google AI Studio / Gemini API Key"
    )
    GEMINI_GENERATION_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Fast multimodal model for generation, routing, grading, rewriting",
    )
    GEMINI_PRO_MODEL: str = Field(
        default="gemini-2.5-pro",
        description="Deep reasoning model for high-stakes generation & self-check",
    )

    # Fallback Providers (100% Free Tiers)
    GROQ_API_KEY: str = Field(default="", description="Groq Cloud API Key (Free tier)")
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile", description="Groq generation model"
    )

    OPENROUTER_API_KEY: str = Field(
        default="", description="OpenRouter API Key (Free tier)"
    )
    OPENROUTER_MODEL: str = Field(
        default="deepseek/deepseek-r1:free",
        description="OpenRouter free model endpoint",
    )

    PROVIDER_PRIORITY: list[str] = ["gemini", "groq", "openrouter"]

    # Embeddings & Reranker (Fixed & Local for 100% zero-cost and crash resilience)
    EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Local fastembed model (fixed vector space)",
    )
    EMBEDDING_DIM: int = 384
    RERANKER_MODEL: str = Field(
        default="ms-marco-TinyBERT-L-2-v2",
        description="Local cross-encoder reranker model (FlashRank ONNX)",
    )

    # Vector Store (Dual mode: Embedded local disk or Qdrant Server / Docker)
    QDRANT_URL: str | None = Field(
        default=None,
        description="Qdrant server URL (e.g. http://localhost:6333). If None, uses local embedded storage",
    )
    QDRANT_PATH: str = Field(
        default="./data/qdrant",
        description="Local disk path for embedded Qdrant vector database",
    )
    QDRANT_COLLECTION: str = "knowledge_base"
    QDRANT_SEMANTIC_CACHE_COLLECTION: str = "semantic_cache"

    # Cache Layer (Dual mode: Redis or embedded local SQLite cache)
    REDIS_URL: str | None = Field(
        default=None,
        description="Redis URL (e.g. redis://localhost:6379/0). If None, uses local embedded cache",
    )
    LOCAL_CACHE_PATH: str = Field(
        default="./data/cache/cache.db",
        description="Local SQLite database file for zero-cost caching",
    )
    EXACT_CACHE_TTL_SECONDS: int = 86400  # 24 hours
    SEMANTIC_CACHE_THRESHOLD: float = (
        0.90  # Cosine similarity threshold for semantic hit
    )

    # Agent Control & Bounds
    MAX_CORRECTION_ATTEMPTS: int = 2
    MAX_GROUNDEDNESS_RETRIES: int = 2
    MAX_RETRIEVAL_RESULTS: int = 8
    RERANK_TOP_K: int = 4

    # Web Search Fallback (Zero cost: DuckDuckGo search)
    ENABLE_WEB_SEARCH_FALLBACK: bool = True

    # Memory Settings (Short-term & Long-term)
    QDRANT_USER_MEMORY_COLLECTION: str = "user_memory"
    SHORT_TERM_MEMORY_MAX_MESSAGES: int = 10  # Token/message budget before summarization
    LONG_TERM_MEMORY_SIMILARITY_THRESHOLD: float = 0.65
    ENABLE_LONG_TERM_MEMORY: bool = True

    # Observability & Metrics
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = Field(
        default=None,
        description="OpenTelemetry OTLP collector gRPC/HTTP endpoint (e.g. http://localhost:4317)",
    )
    OTEL_SERVICE_NAME: str = "amch-rag-service"
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, description="Langfuse public API key")
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, description="Langfuse secret API key")
    LANGFUSE_HOST: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse instance host URL",
    )
    ENABLE_PROMETHEUS: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of the application settings."""
    return Settings()
