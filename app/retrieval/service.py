"""Baseline RAG service orchestrating hybrid retrieval and grounded generation."""

import uuid

from app.gateway.client import ModelGateway
from app.retrieval.models import Citation, QueryRequest, QueryResponse, RetrievedChunk
from app.retrieval.retriever import HybridRetriever

SYSTEM_INSTRUCTION = """You are a precise, grounded assistant. Answer questions using ONLY the provided context.
Cite each factual claim with the source marker [n] matching the corresponding numbered context passage (e.g. [1], [2]).
If the context does not contain enough information to answer the question, state clearly that the knowledge base does not contain the answer.
Do not invent information or make claims not supported by the context."""


class BaselineRAGService:
    """Baseline non-agentic RAG pipeline: Hybrid Retrieval -> Grounded Generation with Citations."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        gateway: ModelGateway | None = None,
    ) -> None:
        """Initialize the baseline RAG service."""
        self.retriever = retriever or HybridRetriever()
        self.gateway = gateway or ModelGateway.get_instance()

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
        """Execute baseline RAG retrieval and synthesis."""
        trace_id = str(uuid.uuid4())

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

        return QueryResponse(
            answer=answer_text.strip(),
            citations=citations,
            provider_used=provider_used,
            trace_id=trace_id,
        )
