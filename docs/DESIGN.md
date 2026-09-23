# DESIGN — AMCH-RAG

Concrete schemas and contracts implementing `ARCHITECTURE.md`. This is the reference the coding agent should implement against; where this doc and library reality disagree (APIs evolve), keep the *intent* and adjust the exact call syntax, then note the deviation in `MEMORY.md`.

## 1. Qdrant Collection Schema

```python
# One collection per corpus, e.g. "knowledge_base"
COLLECTION_CONFIG = {
    "vectors": {
        "dense": {
            "size": 384,
            "distance": "Cosine",
        },  # matches chosen local embedding model's dim
    },
    "sparse_vectors": {
        "sparse": {}  # BM25/SPLADE-style term vector
    },
}


# Payload schema (every point must have all required fields)
class ChunkPayload(BaseModel):
    doc_id: str  # stable id of the source document
    doc_version: int  # incremented on re-ingestion
    source: str  # filename / URL
    source_type: Literal["pdf", "docx", "txt", "md", "html", "csv", "pptx", "image"]
    modality: Literal["text", "table", "image_caption"]
    section: str | None = None  # heading/section path, if known
    page: int | None = None
    chunk_index: int  # position within the parent document
    parent_chunk_id: str | None = None  # for small-to-big retrieval
    access_level: str = "default"  # enforced as a Qdrant filter at query time
    ingested_at: datetime
    content: str  # the chunk text itself (also stored in payload for citation display)
```

Retrieval query (conceptual — hybrid + fusion + filter in one round trip via Qdrant's Query API `prefetch`):
```python
results = qdrant_client.query_points(
    collection_name="knowledge_base",
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=40),
        Prefetch(query=sparse_vector, using="sparse", limit=40),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    query_filter=Filter(
        must=[
            FieldCondition(
                key="access_level", match=MatchValue(value=user_access_level)
            )
        ]
    ),
    limit=20,
)
```

## 2. Cache Schema (Redis)

```
# Exact cache
key:   cache:exact:{sha256(normalized_query)}
value: JSON { "answer": str, "citations": [...], "trace_id": str, "created_at": ... }
ttl:   configurable per query class, default 24h

# Semantic cache — small vector index of recent (query_embedding -> exact cache key)
# Implemented as a secondary Qdrant collection "semantic_cache" or Redis + a lightweight vector index.
# On a new query: embed it, ANN-search this index, if best match score >= SEMANTIC_CACHE_THRESHOLD (default 0.92)
# → fetch the linked exact-cache entry and return it (still passes through output guardrails before streaming).
```
Cache invalidation: when a document is re-ingested/deleted, any cache entry whose citations reference the affected `doc_id` is invalidated (store a reverse index `doc_id -> [cache_keys]`).

## 3. LangGraph State

```python
class AgentState(TypedDict):
    trace_id: str
    query: str
    chat_history: list[BaseMessage]
    user_id: str | None
    access_level: str

    route: Literal["cache", "memory", "retrieve", "tool_call"] | None
    cache_hit: bool
    memory_context: str | None

    retrieved_docs: list[ChunkPayload]
    relevance_grades: list[Literal["relevant", "ambiguous", "irrelevant"]]
    correction_attempts: int
    rewritten_query: str | None
    web_results: list[dict] | None

    draft_answer: str | None
    citations: list[Citation]
    groundedness_score: float | None
    guardrail_flags: list[str]

    final_answer: str | None
```

Graph shape (nodes → conditional edges), matching `ARCHITECTURE.md` §4–5:
`input_guardrails → router → {cache_lookup, memory_lookup, retrieve} → rerank → grade → {generate, rewrite→retrieve, web_fallback→generate} → groundedness_check → {generate (retry, bounded), output_guardrails} → END`

Bound `correction_attempts` and the groundedness-retry counter (config default: 2 each) so the graph can never loop forever.

## 4. Prompt Templates (starting points — tune against `evals/`)

**Router** (cheap/fast model):
```
Given the conversation so far and the new user message, decide the route:
- "cache": near-identical to a question already answered in this conversation
- "memory": answerable purely from known user facts/conversation history, no document lookup needed
- "retrieve": requires looking up the knowledge base
- "tool_call": requires a tool (e.g. current web info) rather than the knowledge base
Return one of: cache | memory | retrieve | tool_call, with a one-line reason.
```

**CRAG Grader** (per retrieved chunk, cheap/fast model):
```
Question: {query}
Retrieved passage: {chunk}
Does this passage contain information that helps answer the question?
Answer exactly one of: relevant | ambiguous | irrelevant. One line of justification.
```

**Query Rewriter**:
```
The original query "{query}" retrieved passages graded mostly irrelevant for this reason: {grader_notes}.
Rewrite the query to retrieve better results — consider synonyms, more specific terms, or splitting into a narrower question. Return only the rewritten query.
```

**Generator** (primary/strongest model):
```
Answer the user's question using ONLY the provided context. Cite each factual claim with the source marker [n] matching the numbered context passage.
If the context does not contain enough information, say so explicitly rather than guessing.

Context:
{numbered_chunks}

Question: {query}
```

**Groundedness / Self-check** (cheap/fast model, separate call from generation):
```
Context passages: {numbered_chunks}
Draft answer: {draft_answer}
For each factual claim in the draft answer, is it directly supported by the context? 
Return: SUPPORTED, PARTIALLY_SUPPORTED, or UNSUPPORTED, plus the specific unsupported claim(s) if any.
```

## 5. API Contract

```
POST /ingest
  multipart file OR { "url": str }
  → { "job_id": str, "status": "queued" }

GET /ingest/{job_id}
  → { "status": "queued|processing|done|failed", "doc_id": str | null, "error": str | null }

POST /query   (Server-Sent Events stream)
  { "query": str, "session_id": str, "access_level": str = "default" }
  stream events:
    { "type": "token", "content": str }
    { "type": "citation", "index": int, "source": str, "chunk_id": str }
    { "type": "correction", "reason": str }         # emitted if a groundedness retry happened
    { "type": "done", "trace_id": str }

GET /documents            → list of ingested docs + versions
DELETE /documents/{doc_id} → soft-delete + cache invalidation

POST /feedback
  { "trace_id": str, "rating": "up" | "down", "comment": str | null }

GET /health   → { "status": "ok", "qdrant": bool, "redis": bool, "providers": {...} }
GET /metrics  → Prometheus exposition format
```

## 6. Config / `.env` Keys

```
# Primary provider (Gemini AI Pro subscription)
GEMINI_API_KEY=
GEMINI_GENERATION_MODEL=gemini-3-flash        # confirm current stable model name at build time
GEMINI_PRO_MODEL=gemini-3.1-pro-preview        # used for final generation if quality > latency matters

# Fallback providers
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b                  # confirm current free-tier model list at build time
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free                # auto-routes to an available free model

PROVIDER_PRIORITY=gemini,groq,openrouter

# Embeddings (fixed, not fallback — see ARCHITECTURE.md §7)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-base

# Infra
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
SEMANTIC_CACHE_THRESHOLD=0.92

# Observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
OTEL_EXPORTER_OTLP_ENDPOINT=

# Guardrails
MAX_CORRECTION_ATTEMPTS=2
MAX_GROUNDEDNESS_RETRIES=2
```

Note: pin exact Gemini/Groq/OpenRouter model IDs at build time — provider model catalogs and free-tier availability change frequently; the gateway should read the model name from config, never hardcode it, precisely so this is a one-line update rather than a code change.

## 7. Guardrail Rule Format
```python
class GuardrailRule(BaseModel):
    name: str
    stage: Literal["input", "output"]
    check: Callable[[str], GuardrailResult]  # or an LLM-judge call via the gateway
    on_fail: Literal["block", "redact", "flag_only"]
```
Rules are registered in a list read at startup (`app/guardrails/registry.py`) so adding a new guardrail is additive, not a change to graph logic.
