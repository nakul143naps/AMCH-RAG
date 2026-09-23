# RULES — Engineering Conventions for AMCH-RAG

These rules bind whichever coding agent (Antigravity, Claude Code, or a human) implements this project from `ARCHITECTURE.md`, `DESIGN.md`, and `TASKS.md`. Follow them exactly unless a task explicitly overrides one.

## 1. Project Structure
```
amch-rag/
├── app/
│   ├── api/              # FastAPI routers (ingest, query, feedback, health)
│   ├── agent/             # LangGraph graph definition, nodes, state schema
│   ├── ingestion/          # Loaders, parsers, chunkers, vision captioning
│   ├── retrieval/          # Hybrid search, reranking, query transformation
│   ├── memory/             # Short-term + long-term memory
│   ├── cache/               # Exact + semantic cache
│   ├── guardrails/          # Input/output guardrail checks
│   ├── gateway/             # Model provider router + failover
│   ├── observability/        # Tracing, metrics, logging setup
│   ├── config.py             # Pydantic Settings, loads from .env
│   └── main.py                # App entrypoint
├── evals/                      # Golden dataset + RAGAS eval scripts
├── tests/                       # Mirrors app/ structure
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```
Every subpackage in `app/` gets its own `tests/` counterpart. Do not add code to `app/main.py` beyond app assembly (routers, middleware, startup/shutdown hooks) — business logic lives in its module.

## 2. Language & Style
- Python 3.11+. Type hints on every function signature — no bare `def foo(x):`.
- Pydantic v2 models for all structured data crossing a boundary (API request/response, LangGraph state, config, cache entries).
- Format with `ruff format`, lint with `ruff check`; both must pass before a task is marked done.
- Prefer composition over inheritance; prefer small pure functions for anything that doesn't need shared state (chunkers, scorers, formatters).
- Docstrings (Google style) on every public function/class — one sentence on *what*, plus *why* if the reason isn't obvious from the code.

## 3. Async & Concurrency
- The API layer is async end-to-end (`async def` route handlers, `httpx.AsyncClient` for outbound calls, async Qdrant/Redis clients).
- CPU-bound work (parsing, chunking, local embedding, local reranking) runs in a worker pool (`asyncio.to_thread` or a dedicated worker process), never blocking the event loop.
- Ingestion of large documents is a background job (return a job ID immediately, poll or webhook for completion) — never a synchronous request that blocks on a multi-minute parse.

## 4. LLM & Provider Rules
- **No module outside `app/gateway/` ever imports a provider SDK directly** (no `google.generativeai`, `groq`, or `openai` client anywhere else in the codebase). Every LLM call goes through the gateway's single call interface, which handles provider selection, retries, and failover.
- Every gateway call must specify: purpose (`generation` / `grading` / `routing` / `groundedness_check` / `query_rewrite`), so cheaper/faster models can be routed to cheap tasks (routing, grading) and the strongest available model reserved for final generation.
- The embedding model is **not** part of gateway failover (see `ARCHITECTURE.md` §7). It is loaded once at startup from a pinned model name in config; changing it requires an explicit migration task, never a runtime fallback.
- Every provider call is wrapped with a timeout and a bounded retry count. No unbounded retry loops.
- Never hardcode a model name inline in business logic — read it from `config.py`, which reads from `.env`.

## 5. Secrets & Config
- All secrets (API keys, Redis/Qdrant URLs if non-default) come from environment variables via a single `Settings` (Pydantic `BaseSettings`) object in `config.py`. Nothing else reads `os.environ` directly.
- `.env` is git-ignored; `.env.example` lists every required key with a placeholder value and a one-line comment on where to get it.
- Never log a secret, API key, or raw PII. Guardrail/logging code must redact before writing to any log or trace sink.

## 6. Guardrails Are Non-Negotiable Gates
- Input guardrails run **before** the router node — no query reaches retrieval or generation unchecked.
- Output guardrails (including the groundedness check) run **before** any token is streamed to the client — do not stream directly from the generator node; buffer, check, then stream (or stream provisionally and emit a correction event if the check fails, per the streaming design in `DESIGN.md`).
- A guardrail failure is a first-class graph outcome (its own state field + edge), not an exception swallowed somewhere.

## 7. Data & Retrieval Rules
- Every chunk written to Qdrant carries the full payload schema from `DESIGN.md` §2 — no partial payloads. Missing required metadata is a hard ingestion error, not a warning.
- Retrieval always applies access-level filtering at the Qdrant query level (`must` filter), never as an in-memory post-filter — don't fetch what a query isn't allowed to see.
- Re-ingesting a previously-ingested source must delete/supersede its prior chunks (by `doc_id` + version), never silently duplicate them.

## 8. Testing
- Every module in `app/` has corresponding tests in `tests/`. Minimum bar: the happy path + at least one failure path (bad input, provider timeout, empty retrieval, etc.) per public function.
- The CRAG loop, the semantic cache threshold behavior, and provider failover each need a dedicated test that simulates the failure condition (mock a bad retrieval, mock a 429 from the primary provider) — these are the parts most likely to silently break.
- `evals/` golden set runs are separate from unit tests (slower, calls real or recorded LLM responses) — wire them as an opt-in CI job, not part of the default fast test suite.

## 9. Observability Rules
- Every request gets a `trace_id` generated at the API boundary and threaded through the entire LangGraph state — every node's span/log carries it.
- Log structured (JSON), not free-text strings, so traces are queryable.
- Any new LLM call, retrieval call, or cache operation added later must emit a span — this is checked in code review, not optional.

## 10. Git / Task Hygiene
- One task from `TASKS.md` per commit/PR where reasonably possible; commit messages reference the task ID (e.g. `feat(ingestion): implement table-aware chunker [Phase 1 / T1.4]`).
- After completing a phase in `TASKS.md`, update `MEMORY.md` with what was decided, what was deviated from the original design (and why), and what's left open — this file is the project's running memory across sessions, keep it current rather than rewriting history.
- Don't silently change an architectural decision from `ARCHITECTURE.md` while implementing — if reality forces a deviation, record it in `MEMORY.md` and, if it's significant, update `ARCHITECTURE.md` itself.

## 11. Performance Budgets (fail a task that blows these without discussion)
- Cache hit round-trip: < 300ms.
- Hybrid retrieval + rerank (no correction loop): < 1.5s.
- Full agentic query including one correction loop: < 8s p95.
- Ingestion: async/background, no hard budget, but must report progress, not just a final success/failure.
