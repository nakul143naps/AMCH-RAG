"""Long-term durable fact extraction, storage in Qdrant, and hybrid retrieval per-user."""

import hashlib
import json
import logging
import uuid

from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    SparseVector,
)

from app.config import Settings, get_settings
from app.gateway.client import ModelGateway
from app.memory.models import UserFact
from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

FACT_EXTRACTION_PROMPT = """You are an expert user memory extraction system.
Analyze the user's message and determine if the user stated any durable personal facts, preferences, background info, or explicit constraints that should be remembered across future sessions.

Examples of durable facts to remember:
- "I prefer answers in Python instead of JavaScript" -> "User prefers code solutions in Python rather than JavaScript"
- "My name is Alice and I am a backend software engineer" -> "User's name is Alice and works as a backend software engineer"
- "I am allergic to penicillin" -> "User is allergic to penicillin"
- "Our company deployment uses AWS us-east-1 with Kubernetes" -> "User's company deployment infrastructure is in AWS us-east-1 using Kubernetes"

Non-durable statements to IGNORE:
- Temporary greetings ("hello", "how are you")
- Routine search queries ("what is cardiac arrest?", "calculate 15 * 4")
- Fleeting commands ("show me line 40", "explain that simpler")

Conversation turn:
User message: "{user_message}"
Assistant response: "{assistant_response}"

Respond in JSON format:
{{
  "facts": ["Fact 1", "Fact 2"]
}}
If no durable facts are present, return: {{"facts": []}}"""


class UserMemoryService:
    """Manages long-term durable user facts stored in Qdrant with hybrid dense+sparse embeddings."""

    _instance: "UserMemoryService | None" = None

    @classmethod
    def get_instance(
        cls,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
        gateway: ModelGateway | None = None,
    ) -> "UserMemoryService":
        if cls._instance is None:
            cls._instance = UserMemoryService(
                vector_mgr=vector_mgr,
                embedding_engine=embedding_engine,
                gateway=gateway,
            )
        return cls._instance

    def __init__(
        self,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
        gateway: ModelGateway | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()
        self.embedding_engine = embedding_engine or EmbeddingEngine.get_instance()
        self.gateway = gateway or ModelGateway.get_instance()
        self.settings = settings or get_settings()

    async def extract_facts(
        self, user_message: str, assistant_response: str = ""
    ) -> list[str]:
        """Use the LLM gateway to extract durable user facts and preferences from dialogue."""
        if not user_message or len(user_message.strip()) < 5:
            return []

        prompt = FACT_EXTRACTION_PROMPT.format(
            user_message=user_message.strip(),
            assistant_response=assistant_response.strip(),
        )

        try:
            raw_json, _ = await self.gateway.generate(
                prompt=prompt,
                purpose="memory_extraction",
                system_instruction="You extract durable user facts and output strictly valid JSON.",
            )
            # Clean possible markdown fencing
            cleaned = raw_json.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            parsed = json.loads(cleaned)
            facts = parsed.get("facts", [])
            return [f.strip() for f in facts if isinstance(f, str) and f.strip()]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Fact extraction failed for message '{user_message}': {e}")
            return []

    def store_fact(self, user_id: str, fact_text: str, category: str = "preference") -> UserFact:
        """Store a durable user fact into Qdrant user_memory collection with dense and sparse vectors."""
        self.vector_mgr.ensure_collections()
        col = self.settings.QDRANT_USER_MEMORY_COLLECTION

        fact = UserFact(
            user_id=user_id,
            fact=fact_text.strip(),
            category=category,
        )

        # Dense embedding
        dense_vec = self.embedding_engine.embed_dense([fact.fact])[0]
        # Sparse BM25 embedding
        sparse_vec = self.embedding_engine.embed_sparse([fact.fact])[0]

        # Deterministic UUID based on user_id and fact content to prevent duplicates
        fact_hash = hashlib.sha256(f"{user_id}:{fact.fact.lower()}".encode()).hexdigest()
        point_id = str(uuid.UUID(fact_hash[:32]))

        payload = {
            "fact_id": fact.fact_id,
            "user_id": user_id,
            "fact": fact.fact,
            "category": fact.category,
            "created_at": fact.created_at,
            "source_type": "user_memory",
        }

        point = PointStruct(
            id=point_id,
            vector={
                "dense": dense_vec,
                "sparse": SparseVector(
                    indices=sparse_vec.indices,
                    values=sparse_vec.values,
                ),
            },
            payload=payload,
        )

        self.vector_mgr.client.upsert(
            collection_name=col,
            points=[point],
        )
        logger.info(f"UserMemoryService: Stored fact for user '{user_id}': '{fact.fact}'")
        return fact

    async def async_store_facts(
        self, user_id: str, facts: list[str], category: str = "preference"
    ) -> list[UserFact]:
        """Store a list of extracted facts for a user."""
        stored = []
        for f in facts:
            fact_obj = self.store_fact(user_id=user_id, fact_text=f, category=category)
            stored.append(fact_obj)
        return stored

    def search_user_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[UserFact]:
        """Retrieve relevant durable facts for a user given a query."""
        if not user_id:
            return []

        self.vector_mgr.ensure_collections()
        col = self.settings.QDRANT_USER_MEMORY_COLLECTION

        dense_vec = self.embedding_engine.embed_dense([query])[0]
        sparse_vec = self.embedding_engine.embed_sparse([query])[0]

        user_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                )
            ]
        )

        points = self.vector_mgr.query_hybrid(
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            limit=limit,
            query_filter=user_filter,
            collection_name=col,
        )

        results: list[UserFact] = []
        for p in points:
            payload = p.payload or {}
            results.append(
                UserFact(
                    fact_id=payload.get("fact_id", str(p.id)),
                    user_id=payload.get("user_id", user_id),
                    fact=payload.get("fact", ""),
                    category=payload.get("category", "preference"),
                    created_at=payload.get("created_at", ""),
                )
            )

        return results

    def get_all_user_facts(self, user_id: str, limit: int = 50) -> list[UserFact]:
        """Retrieve all durable facts for a user."""
        if not user_id:
            return []

        self.vector_mgr.ensure_collections()
        col = self.settings.QDRANT_USER_MEMORY_COLLECTION

        user_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                )
            ]
        )

        points, _ = self.vector_mgr.client.scroll(
            collection_name=col,
            scroll_filter=user_filter,
            limit=limit,
            with_payload=True,
        )

        return [
            UserFact(
                fact_id=p.payload.get("fact_id", str(p.id)),
                user_id=p.payload.get("user_id", user_id),
                fact=p.payload.get("fact", ""),
                category=p.payload.get("category", "preference"),
                created_at=p.payload.get("created_at", ""),
            )
            for p in points
            if p.payload
        ]
