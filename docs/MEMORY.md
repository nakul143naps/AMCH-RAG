# MEMORY — AMCH-RAG Project Memory

This file is the project's running memory. Whoever (or whatever) is implementing this — update it after every phase in `TASKS.md`, and any time a decision deviates from `ARCHITECTURE.md`/`DESIGN.md`. Keep entries dated and short. Don't delete old entries — append.

## Project State
**Current phase**: Phase 5 — Caching. Phase 4 complete.

## Key Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| Spec creation | Python + LangChain/LangGraph for orchestration | User wants an "advanced agentic RAG"; LangGraph is what gives real branching/looping control (router, CRAG loop, self-check) rather than a linear chain |
| Spec creation | Qdrant, self-hosted/local, as vector store | Native hybrid (dense+sparse+RRF) search in one query, user-specified preference |
| Spec creation | Gemini (via user's Gemini AI Pro subscription) as primary LLM; Groq then OpenRouter as automatic fallback | User wants provider resilience ("if one model is down other should backup"); Groq/OpenRouter both have real free tiers as of research at spec time |
| Spec creation | Embedding model is fixed/local (fastembed), **not** part of the provider-failover chain | Different embedding models produce incompatible vector spaces; silently failing over embeddings would quietly corrupt retrieval quality. See `ARCHITECTURE.md` §7 |
| Spec creation | Reranker is local (cross-encoder via fastembed) by default | Removes another external dependency/cost; can be swapped for a hosted reranker later if quality demands it |
| Spec creation | Two-tier cache: exact (Redis, normalized query hash) + semantic (embedding similarity, threshold configurable) | Directly answers the "already answered / similar question" requirement from the brief |
| Spec creation | Web search fallback only triggers after CRAG correction attempts are exhausted, and is explicitly labeled as web-sourced | Keeps knowledge-base answers and open-web answers distinguishable to the user |
| Phase 0 Setup | Prioritize Gemini AI Pro capabilities + 100% free/local/open-source tooling | User directive: ensure database, cache, fallbacks, and tools are free/local (embedded Qdrant + local SQLite cache fallback + free DuckDuckGo search + Groq/OpenRouter free tiers), while leveraging Gemini AI Pro as the primary model |

## Config / Model Names to Re-Verify Before Building
Provider free tiers and model catalogs move fast. At build time (not spec time), re-check and update `.env` accordingly — don't trust the exact model ID strings below without a fresh check:
- Current Gemini generation model IDs and which are covered by the free tier vs. require the Pro subscription/paid usage.
- Current Groq free-tier model list and rate limits (these are known to change — see the `.env.example` comment in `DESIGN.md` §6).
- Current OpenRouter free model list / whether `openrouter/free` auto-routing is still the recommended pattern.
- Whether Google Antigravity CLI's current headless invocation flags (`agy -p ... --output-format stream-json --non-interactive --model ...`) match what's installed, since flag surfaces on fast-moving CLI tools can change between versions.

## Known Open Questions (from `PRD.md` §10)
- [ ] Exact chunk sizes/overlap per content type — tune against eval results once Phase 12 eval harness exists.
- [ ] Web-search provider for CRAG fallback — decide during Phase 7.
- [ ] Whether a lightweight web UI ships in v1.

- _Phase 4 Reranker Engine_: Swapped local reranker implementation from raw FastEmbed to FlashRank (`ms-marco-TinyBERT-L-2-v2`). FlashRank provides ultra-lightweight ONNX-quantized models (~3MB) with sub-10ms CPU inference and zero PyTorch/GPU dependencies, avoiding heavy wheel downloads on Windows while maintaining high-quality cross-attention.

## Environment Notes
- Required `.env` keys: see `DESIGN.md` §6. Never commit a filled `.env`.
- Local services expected: Qdrant (6333), Redis (6379), API (8000) — see `docker-compose.yml` once created in Phase 0.

## Changelog
- _Spec creation_: Initial `PRD.md`, `ARCHITECTURE.md`, `RULES.md`, `DESIGN.md`, `TASKS.md`, `MEMORY.md` written based on requirements: agentic, multi-modal, corrective, hybrid RAG with guardrails, caching, memory, observability, reranking, and multi-provider LLM resilience (Gemini primary, Groq/OpenRouter fallback), Qdrant self-hosted.
- _Phase 0 completed_: Environment initialized with `uv` (Python 3.12). Core structure created. Pydantic Settings, local Qdrant embedded/remote manager, multi-backend cache with SQLite fallback, Gemini primary LLM client with Groq/OpenRouter resilience, and health check route created and verified.
- _Phase 1 completed_: Core ingestion pipeline implemented and verified. Supports TXT, Markdown (section-aware), DOCX (paragraph + table), and PDF. Recursive boundary-aware semantic chunker built. FastEmbed dense (`BAAI/bge-small-en-v1.5`) and sparse (`Qdrant/bm25`) embeddings wired. Qdrant schema compliance verified. Async `POST /ingest` background tasks and `GET /ingest/{job_id}` tracking verified. 13/13 tests passing.
- _Phase 2 completed_: Hybrid Retrieval implemented and verified. Built `HybridRetriever` and `VectorStoreManager.query_hybrid` executing single-roundtrip dense + BM25 sparse queries fused via native Reciprocal Rank Fusion (RRF). Added tenant isolation via Qdrant query-level `access_level` filter and metadata filtering (`doc_ids`, `source_types`). Implemented async worker pool offloading via `asyncio.to_thread`. 19/19 tests passing.
- _Phase 3 completed_: Baseline RAG implemented and verified. Built `BaselineRAGService` formatting numbered context passages with source, section, and page citations. Built non-streaming `POST /query` endpoint returning answer + structured citations (`Citation` schema). Handled empty retrieval and provider error paths with appropriate status codes. 23/23 tests passing.
- _Phase 4 completed_: Local cross-encoder reranker implemented and verified. Built `RerankerService` leveraging FlashRank ONNX (`ms-marco-TinyBERT-L-2-v2`). Wired into two-stage retrieval (top-$N$ candidate prefetch $\to$ cross-attention scoring $\to$ top-$k$ output). Created comparative evaluation benchmark demonstrating measurable Top-1 precision improvement over keyword distractor traps. 27/27 tests passing.
