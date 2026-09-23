"""Baseline RAG service orchestrating hybrid retrieval and grounded generation."""

import uuid

from app.cache.service import TwoTierCacheService
from app.gateway.client import ModelGateway
from app.retrieval.models import Citation, QueryRequest, QueryResponse, RetrievedChunk
from app.retrieval.retriever import HybridRetriever

SYSTEM_INSTRUCTION = """You are a precise, grounded assistant. Answer questions using ONLY the provided context.
Cite each factual claim with the source marker [n] matching the corresponding numbered context passage (e.g. [1], [2]).
If the context does not contain enough information to answer the question, state clearly that the knowledge base does not contain the answer.
Do not invent information or make claims not supported by the context."""


class BaselineRAGService:
    """Baseline non-agentic RAG pipeline: Two-Tier Cache -> Hybrid Retrieval -> Grounded Generation with Citations."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        gateway: ModelGateway | None = None,
        cache_service: TwoTierCacheService | None = None,
    ) -> None:
        """Initialize the baseline RAG service."""
        self.retriever = retriever or HybridRetriever()
        self.gateway = gateway or ModelGateway.get_instance()
        self.cache_service = cache_service or TwoTierCacheService.get_instance()

    def _format_context(
        self, chunks: list[RetrievedChunk]
    ) -> tuple[str, list[Citation]]:
        """Format retrieved chunks into numbered context passages and corresponding citation models."""
        formatted_passages: list[str] = []
        citations: list[Citation] = []

        for i, chunk in enumerate(chunks):
            idx = i + 1
            meta_desc = f"Source: {chunk.source}"
            if chunk.section:
                meta_desc += f", Section: {chunk.section}"
            if chunk.page is not None:
                meta_desc += f", Page: {chunk.page}"

            formatted_passages.append(f"[{idx}] ({meta_desc})\n{chunk.content.strip()}")

            snippet = chunk.content.strip()
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."

            citations.append(
                Citation(
                    index=idx,
                    source=chunk.source,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    section=chunk.section,
                    page=chunk.page,
                    snippet=snippet,
                )
            )

        return "\n\n".join(formatted_passages), citations

    async def answer(self, request: QueryRequest) -> QueryResponse:
        """Execute baseline RAG retrieval and synthesis with Two-Tier Caching."""
        trace_id = str(uuid.uuid4())

        # Step 0: Check Two-Tier Cache (Exact & Semantic)
        if not request.skip_cache:
            cached_entry, hit_type = await self.cache_service.async_lookup(
                query=request.query, access_level=request.access_level
            )
            if cached_entry:
                cached_citations = [
                    Citation(**c) for c in cached_entry.get("citations", [])
                ]
                return QueryResponse(
                    answer=cached_entry["answer"],
                    citations=cached_citations,
                    provider_used=f"cache:{hit_type}",
                    trace_id=cached_entry.get("trace_id", trace_id),
                )

        # 1. Retrieve relevant chunks
        chunks = await self.retriever.async_retrieve(
            query=request.query,
            limit=request.limit,
            mode=request.mode,
            access_levels=request.access_level,
            rerank=request.rerank,
        )

        # 2. Check for empty retrieval
        if not chunks:
            return QueryResponse(
                answer="I could not find any relevant information in the knowledge base to answer your question.",
                citations=[],
                provider_used="none",
                trace_id=trace_id,
            )

        # 3. Format context and build citations
        context_text, citations = self._format_context(chunks)

        prompt = (
            f"Context passages:\n{context_text}\n\nQuestion: {request.query}\n\nAnswer:"
        )

        # 4. Generate answer via Model Gateway
        answer_text, provider_used = await self.gateway.generate(
            prompt=prompt,
            purpose="generation",
            system_instruction=SYSTEM_INSTRUCTION,
        )

        # 5. Store in Two-Tier Cache
        doc_ids = list({c.doc_id for c in chunks})
        await self.cache_service.async_store(
            query=request.query,
            access_level=request.access_level,
            answer=answer_text.strip(),
            citations=[c.model_dump() for c in citations],
            doc_ids=doc_ids,
            trace_id=trace_id,
        )

        return QueryResponse(
            answer=answer_text.strip(),
            citations=citations,
            provider_used=provider_used,
            trace_id=trace_id,
        )
