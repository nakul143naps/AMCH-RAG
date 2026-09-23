# PRD — Agentic Multi-Modal Corrective Hybrid RAG (AMCH-RAG)

## 1. Vision
Build a **production-grade, self-correcting, multi-modal Retrieval-Augmented Generation system** that behaves like a careful research assistant rather than a naive "embed and stuff into context" pipeline. It should know when it already knows the answer (cache/memory), know when its own retrieval is bad and fix itself (corrective loop), understand documents the way a human would (text, tables, charts, images), and never silently hallucinate.

This is not a demo RAG. Every stage — retrieval, generation, and output — is checked before it reaches the user.

## 2. Problem Statement
Naive RAG fails in predictable ways:
- It retrieves even when retrieval isn't needed (simple/greeting queries, or questions already answered in the conversation).
- It re-does expensive retrieval + generation for questions that are semantically identical to ones already answered.
- It trusts whatever the vector search returns, even when the top-k chunks are irrelevant.
- It can't read a table, chart, or scanned page — it just sees garbled text or nothing.
- It has no memory of the user or the conversation beyond the current turn.
- It has one LLM provider; if that provider rate-limits or goes down, the whole system stops.
- Nobody can tell *why* an answer was wrong after the fact — there's no trace.

## 3. Goals
1. **Correctness first** — every answer is grounded, graded, and (if ungrounded) corrected before it's shown to the user.
2. **Speed where it's earned** — semantic cache and memory short-circuit repeat/similar questions; retrieval only runs when actually needed.
3. **Omnivorous ingestion** — PDFs (including scanned/table-heavy), DOCX, TXT/MD, HTML/websites, images, CSV, and PPTX, with tables/charts/graphs/images understood, not just OCR'd.
4. **Safe by construction** — guardrails on the way in (prompt injection, PII, jailbreaks) and on the way out (hallucination, toxicity, unauthorized content).
5. **Observable** — every request is traceable end-to-end: what was retrieved, why, what it cost, how long it took, and whether it was later flagged as wrong.
6. **Resilient** — no single LLM provider outage takes the system down.

## 4. Non-Goals (v1)
- Fine-tuning any model.
- A polished consumer-facing UI (a minimal chat/testing UI is enough; the API is the real product).
- Multi-tenant billing/usage metering (the design should not block it later, but it isn't built now).
- Video ingestion (audio/video transcripts are a fast-follow, not v1).

## 5. Users & Use Cases
- **You (builder/operator)**: ingest a personal/team knowledge base (docs, PDFs, scraped pages) and query it via API or a simple chat UI.
- **Downstream apps**: call the `/query` endpoint as a backend RAG service from another product.
- **Evaluators**: run the eval harness against a golden Q&A set to catch regressions before shipping a change.

## 6. Functional Requirements

### 6.1 Ingestion
- FR-1: Accept PDF, DOCX, TXT, MD, HTML, CSV, PPTX, and common image formats (PNG/JPG) as upload or URL.
- FR-2: Crawl and ingest a website (single page or shallow crawl with depth/domain limits).
- FR-3: Detect and separately handle **tables** (serialize to Markdown, preserve structure) and **charts/graphs/images** (caption + extract data via a vision-capable model).
- FR-4: Chunk content using a strategy appropriate to its type (semantic chunking for prose, table-aware chunking for tables, small-to-big/parent-child chunking for long documents).
- FR-5: Support re-ingestion / update / delete of a source document without duplicating stale chunks (versioned upserts).
- FR-6: Attach rich metadata to every chunk: source, page/section, modality, doc version, ingestion timestamp, access level.

### 6.2 Retrieval
- FR-7: Hybrid search — dense (semantic) + sparse (lexical/BM25) retrieval fused via Reciprocal Rank Fusion.
- FR-8: Query transformation — multi-query expansion, HyDE, and decomposition for complex/multi-part questions.
- FR-9: Reranking of the fused candidate set before it reaches the generator.
- FR-10: Metadata filtering (by source, date range, doc type, access level) at retrieval time.

### 6.3 Agentic Control Flow
- FR-11: A **router** decides, per incoming query, whether to: answer from cache, answer from memory/conversation, retrieve and answer, or call a tool (e.g., web search) — instead of always retrieving.
- FR-12: **Corrective RAG loop** — retrieved chunks are graded for relevance; if the grade is low, the system rewrites the query and retries, and/or falls back to web search, before generating an answer.
- FR-13: **Self-check before responding** — a groundedness/faithfulness check verifies the draft answer is supported by the retrieved context; ungrounded answers are regenerated or qualified with an explicit "I'm not confident" signal rather than shown as fact.
- FR-14: The agent can be extended with additional tools (calculator, code execution, structured DB lookup) without changing its core graph shape.

### 6.4 Caching & Memory
- FR-15: **Exact cache** — identical (or near-identical, normalized) queries return the cached answer instantly.
- FR-16: **Semantic cache** — queries that are semantically equivalent to a recently answered query (above a similarity threshold) reuse the cached answer, with a way to force-bypass for freshness-sensitive queries.
- FR-17: **Short-term memory** — conversation history is summarized/compressed as it grows, not just concatenated forever.
- FR-18: **Long-term memory** — durable facts about the user/session (preferences, prior clarifications) persist across sessions and are retrievable like any other memory.

### 6.5 Safety / Guardrails
- FR-19: Input guardrails: prompt-injection detection (including injected instructions hidden inside retrieved documents), jailbreak detection, PII detection/redaction before logging.
- FR-20: Output guardrails: groundedness/faithfulness scoring, toxicity/safety filtering, citation verification (claims map to actual retrieved sources), refusal on unsafe requests.
- FR-21: Document-level access control — a chunk is only retrievable by a query that has permission for its access level.

### 6.6 Multi-Provider Resilience
- FR-22: LLM calls go through a **model gateway** with a configurable provider priority list and automatic failover (e.g., primary provider rate-limited/down → next provider) with retry + circuit breaker, transparent to the rest of the system.
- FR-23: The embedding model used for indexing is fixed and versioned — switching embedding providers requires a re-embedding migration, not a silent runtime fallback (see `ARCHITECTURE.md` §7 for why).

### 6.7 Observability & Evaluation
- FR-24: Full request tracing: router decision, cache hit/miss, retrieved chunks + scores, rewrite attempts, model/provider used, tokens, cost, latency per stage.
- FR-25: An automated eval harness (golden Q&A set) scores faithfulness, answer relevancy, and context precision/recall on demand and in CI.
- FR-26: User feedback (thumbs up/down + free text) is captured and linked to the trace that produced the answer.

### 6.8 API
- FR-27: `POST /ingest` (file/URL), `POST /query` (streaming), `GET /documents`, `DELETE /documents/{id}`, `POST /feedback`, `GET /health`, `GET /metrics`.
- FR-28: Streamed answers include inline citation markers tied to specific source chunks.

## 7. Non-Functional Requirements
| Category | Requirement |
|---|---|
| Latency | Cache hit < 300ms; full agentic query (cold, with correction) < 8s p95 |
| Cost | Default to free/low-cost providers where quality allows; every LLM call logged with token + cost estimate |
| Availability | No single LLM provider outage causes a full outage (automatic failover) |
| Scalability | Ingestion and query paths are async and horizontally scalable; vector store scales independently |
| Security | Secrets never logged; PII redacted before persistence in logs/traces; access control enforced at retrieval |
| Extensibility | New document loaders, tools, and providers can be added via a registered plugin, not core-code surgery |

## 8. Success Metrics
- ≥90% faithfulness score on the golden eval set.
- ≥95% of semantically-repeated queries served from cache without a full retrieval+generation round-trip.
- 100% of provider outages (simulated) result in automatic failover, not a failed request.
- Every response is traceable end-to-end in the observability backend.

## 9. Assumptions & Constraints
- Python 3.11+, LangChain + LangGraph for orchestration.
- Qdrant, self-hosted (Docker), as the vector store.
- Google Gemini (Gemini AI Pro subscription) as the primary LLM, with Groq and OpenRouter free tiers as automatic fallback.
- Single-operator / small-team scale initially; design should not preclude scaling later.

## 10. Open Questions (track in `MEMORY.md`)
- Exact chunk sizes/overlap per content type — start with defaults in `DESIGN.md`, tune against eval results.
- Whether web-search fallback (for CRAG) uses a paid search API or a free one — pick during Phase 7 (`TASKS.md`).
- Whether a lightweight web UI ships in v1 or the API is the only surface for now.
