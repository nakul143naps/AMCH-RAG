# TASKS — Build Plan for AMCH-RAG

Work phases in order — each phase produces something runnable/testable before the next begins. Check items off as completed; when a phase finishes, update `MEMORY.md` (per `RULES.md` §10) before starting the next.

## Phase 0 — Scaffolding
- [x] Create project structure per `RULES.md` §1.
- [x] `pyproject.toml` with dependencies: fastapi, uvicorn, langchain, langgraph, qdrant-client, redis, fastembed, pydantic-settings, httpx, unstructured (or docling), trafilatura, playwright, ragas, opentelemetry-*, langfuse.
- [x] `docker-compose.yml`: qdrant, redis, api, worker (langfuse/prometheus/grafana optional profiles).
- [x] `config.py` (Pydantic Settings) + `.env.example` per `DESIGN.md` §6.
- [x] `GET /health` returns real status of Qdrant/Redis/provider reachability.
- **Done when**: `docker compose up` starts all services and `/health` returns ok.

## Phase 1 — Core Ingestion (text-only first)
- [x] `DocumentLoader` interface + implementations for TXT/MD/PDF (text-only)/DOCX.
- [x] Semantic chunker (prose) with configurable size/overlap.
- [x] Local embedding model wired up (`fastembed`, pinned per `DESIGN.md` §6).
- [x] Qdrant collection created per schema in `DESIGN.md` §1; upsert pipeline working.
- [x] `POST /ingest` + `GET /ingest/{job_id}` as async background job.
- **Done when**: a PDF/DOCX/TXT file can be ingested end-to-end and its chunks are visible in Qdrant with full payload.

## Phase 2 — Hybrid Retrieval
- [x] Sparse vector generation (BM25/SPLADE via fastembed) added to ingestion.
- [x] Hybrid query (`prefetch` + RRF fusion) implemented per `DESIGN.md` §1.
- [x] Metadata/access-level filtering at query time.
- **Done when**: a query returns fused dense+sparse results with correct filtering, verified against a small hand-built test corpus.

## Phase 3 — Baseline RAG (no agent yet)
- [x] Simple retrieve → generate chain through the model gateway (Phase 11 can be stubbed with Gemini-only for now).
- [x] Minimal `POST /query` (non-streaming) returning an answer + citations.
- **Done when**: you can ask a question about ingested docs and get a cited answer. This is the baseline everything after this phase must beat in eval score.

## Phase 4 — Reranking
- [x] Local cross-encoder reranker wired into the retrieval path (rerank top-N before top-k selection).
- [x] Eval: compare answer relevancy/context precision with vs. without reranking on a small test set.
- **Done when**: reranking measurably improves top-k precision on the test set.

## Phase 5 — Caching
- [x] Exact cache (Redis) on normalized query.
- [x] Semantic cache (embed + ANN match against recent Q&A) with configurable threshold.
- [x] Cache invalidation on document re-ingest/delete.
- **Done when**: an identical query is served from cache in < 300ms, and a paraphrased-but-equivalent query also hits cache above the threshold.

## Phase 6 — Agentic Orchestration (LangGraph)
- [x] `AgentState` per `DESIGN.md` §3.
- [x] Router node (cache / memory / retrieve / tool_call).
- [x] Wire Phases 2–5 into graph nodes instead of a linear chain.
- **Done when**: a greeting or already-cached question skips retrieval entirely (verified via trace), and a knowledge-base question still retrieves correctly. (Verified in tests: greetings and cached queries bypass retrieval, knowledge-base questions retrieve, rerank, and synthesize with citations).

## Phase 7 — Corrective RAG (CRAG)
- [x] Grader node (per-chunk relevance grading).
- [x] Query rewriter node + retry edge (bounded by `MAX_CORRECTION_ATTEMPTS`).
- [x] Web search fallback tool (DuckDuckGo search free-tier fallback with multi-backend resilience) + clearly-labeled web-sourced answers.
- **Done when**: a deliberately hard/ambiguous query triggers a rewrite-and-retry, visible in the trace, and an out-of-corpus query correctly falls back to web search rather than hallucinating. (Verified in tests: ambiguous/irrelevant queries trigger bounded rewrite loop; out-of-corpus queries fall back to web search returning `[Web-Sourced Answer]` with web citations; 53/53 tests passing).

## Phase 8 — Self-RAG / Groundedness + Guardrails
- [x] Groundedness check node (separate LLM-as-judge call, per `DESIGN.md` §4).
- [x] Regeneration-on-ungrounded edge, bounded by `MAX_GROUNDEDNESS_RETRIES`.
- [x] Input guardrails: prompt-injection detection (user message *and* retrieved content), PII redaction before logging.
- [x] Output guardrails: toxicity/safety check, citation verification.
- **Done when**: a deliberately injected instruction inside a test document does not get followed, and a deliberately unsupported claim in a forced-bad draft answer is caught and corrected. (Verified in tests: prompt-injected user query blocked immediately at input gate; injected instruction in document neutralized and ignored by generator; forced-bad draft with unsupported Mars hallucination caught by groundedness judge and regenerated with factually supported claims; 63/63 tests passing).

## Phase 9 — Multi-Modal Ingestion
- [ ] Layout-aware PDF/DOCX/PPTX parsing (table/figure region detection).
- [ ] Table serialization to Markdown as its own chunk type.
- [ ] Vision captioning pass for charts/images (via Gemini multimodal), stored as `image_caption` chunks.
- [ ] Website ingestion (`trafilatura` + `playwright` for JS-rendered pages) + CSV loader.
- **Done when**: a PDF containing a table and a chart is ingested such that a question about a specific table value and a question about the chart's trend are both answerable.

## Phase 10 — Memory
- [ ] Short-term: conversation buffer + summarization once over a token budget (LangGraph checkpointer).
- [ ] Long-term: fact extraction + storage per-user, retrievable via the same hybrid search.
- **Done when**: a fact stated by the user in one session is correctly recalled in a later session.

## Phase 11 — Multi-Provider Model Gateway
- [ ] Gateway interface (`generate`, `grade`, `route`, `check_groundedness`, `rewrite_query` — each tagged with a "purpose" per `RULES.md` §4).
- [ ] Gemini adapter (primary).
- [ ] Groq adapter (fallback 1), OpenRouter adapter (fallback 2).
- [ ] Retry + exponential backoff + circuit breaker + failover chain per `PROVIDER_PRIORITY`.
- [ ] Replace every direct provider call from earlier phases with a gateway call.
- **Done when**: simulating a 429/500 from the primary provider transparently falls through to the next provider without a failed request, verified by a test.

## Phase 12 — Observability & Eval
- [ ] OpenTelemetry spans on every node; `trace_id` threaded through `AgentState`.
- [ ] Langfuse (or equivalent) wired for LLM-specific traces (prompt/completion/cost/latency).
- [ ] Prometheus metrics: cache hit rate, correction-loop rate, groundedness pass rate, failover count, latency histograms.
- [ ] Golden Q&A dataset (start with 20–30 hand-written Q&A pairs against the test corpus) + RAGAS eval script.
- **Done when**: a full request is traceable end-to-end in the tracing UI, and the eval script produces faithfulness/relevancy/precision/recall numbers you can compare across changes.

## Phase 13 — API Polish & Streaming
- [ ] `POST /query` streaming (SSE) with interleaved token/citation/correction events per `DESIGN.md` §5.
- [ ] `POST /feedback` linked to `trace_id`.
- [ ] `GET /documents`, `DELETE /documents/{id}` with cache invalidation.
- [ ] (Optional) minimal chat UI for manual testing.
- **Done when**: you can hold a multi-turn streamed conversation against the API with visible citations and working feedback capture.

## Phase 14 — Hardening & Deployment
- [ ] Full test suite green (`RULES.md` §8), including the failure-path tests for CRAG, cache, and failover.
- [ ] Load-check performance budgets from `RULES.md` §11.
- [ ] Security pass: secrets audit, PII redaction verified in logs, access-level filtering verified with a negative test.
- [ ] README with setup instructions + architecture summary pointing back to `ARCHITECTURE.md`.
- **Done when**: a clean `docker compose up` on a fresh machine, plus `.env` filled in, gets you a working ingest → query round trip with no manual steps beyond that.
