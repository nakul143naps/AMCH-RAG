"""Generation node synthesizing grounded answers with citations and caching results."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.cache.service import TwoTierCacheService
from app.gateway.client import ModelGateway
from app.retrieval.models import Citation, RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are a precise, grounded assistant. Answer questions using ONLY the provided context.
Cite each factual claim with the source marker [n] matching the corresponding numbered context passage (e.g. [1], [2]).
If the context does not contain enough information to answer the question, state clearly that the knowledge base does not contain the answer.
Do not invent information or make claims not supported by the context."""

WEB_SYSTEM_INSTRUCTION = """You are a precise, grounded assistant.
Note: The internal knowledge base did not contain sufficient information, so the following context was retrieved via external web search fallback.
Synthesize an answer using ONLY the provided web context passages.
Clearly state that this information is sourced from external web search.
Cite each factual claim with [n] matching the corresponding numbered web passage.
Do not invent information or extrapolate beyond the provided web sources."""

DIRECT_SYSTEM_INSTRUCTION = """You are a knowledgeable, helpful, and concise AI assistant.
Answer the user's question clearly, comprehensively, and accurately using your pre-trained general knowledge.
Provide a natural, well-structured answer without needing document citations."""


class GenerateNode:
    """Synthesizes answers grounded in retrieved passages with verifiable citations."""

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        cache_service: TwoTierCacheService | None = None,
    ) -> None:
        self.gateway = gateway or ModelGateway.get_instance()
        self.cache_service = cache_service or TwoTierCacheService.get_instance()

    def _format_context(
        self, chunks: list[RetrievedChunk]
    ) -> tuple[str, list[Citation]]:
        """Format chunks into numbered context passages and citation objects."""
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

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Generate answer from retrieved chunks or return zero-context fallback."""
        chunks = state.get("retrieved_docs", [])
        query = state.get("query", "").strip()
        trace_id = state.get("trace_id", "")
        access_level = state.get("access_level", "default")

        is_web_sourced = bool(state.get("web_results")) or any(
            c.doc_id == "web_search" or (c.metadata and c.metadata.get("source_type") == "web")
            for c in chunks
        )

        # Zero-token guard for empty retrieval
        if not chunks:
            # Self-RAG: Direct generation path for general or memory queries that need no retrieval
            if state.get("route") in ("direct", "memory"):
                logger.info(
                    f"GenerateNode generating direct answer without retrieval for: '{query}' (route: {state.get('route')})"
                )
                prompt_parts = []
                chat_history = state.get("chat_history", [])
                if chat_history:
                    prior_turns = chat_history[:-1] if getattr(chat_history[-1], 'content', '') == query else chat_history
                    if prior_turns:
                        history_lines = [
                            f"{'User' if getattr(m, 'type', None) == 'human' else 'Assistant'}: {getattr(m, 'content', str(m))}"
                            for m in prior_turns[-20:]
                        ]
                        prompt_parts.append("Recent Conversation History:\n" + "\n".join(history_lines))

                memory_context = state.get("memory_context")
                if memory_context:
                    prompt_parts.append(f"User & Conversation Memory:\n{memory_context.strip()}")
                prompt_parts.append(f"Question: {query}\n\nAnswer:")
                prompt = "\n\n".join(prompt_parts)

                answer_text, provider_used = await self.gateway.generate(
                    prompt=prompt,
                    purpose="generation",
                    system_instruction=DIRECT_SYSTEM_INSTRUCTION,
                )
                clean_answer = answer_text.strip()

                try:
                    await self.cache_service.async_store(
                        query=query,
                        access_level=access_level,
                        answer=clean_answer,
                        citations=[],
                        doc_ids=[],
                        trace_id=trace_id,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Failed to store direct response in cache: {e}")

                return {
                    "draft_answer": clean_answer,
                    "final_answer": clean_answer,
                    "citations": [],
                    "provider_used": provider_used,
                }

            logger.info(
                "GenerateNode received 0 chunks -> returning zero-context fallback"
            )
            if state.get("web_results") is not None:
                no_info_msg = "I could not find any relevant information in the internal knowledge base or external web search to answer your question."
            else:
                no_info_msg = "I could not find any relevant information in the knowledge base to answer your question."
            return {
                "draft_answer": no_info_msg,
                "final_answer": no_info_msg,
                "citations": [],
                "provider_used": "none",
            }

        # Format context and citations
        context_text, citations = self._format_context(chunks)
        prompt_parts = []

        memory_context = state.get("memory_context")
        if memory_context:
            prompt_parts.append(f"User & Conversation Memory:\n{memory_context.strip()}")

        prompt_parts.append(f"Context passages:\n{context_text}")
        prompt_parts.append(f"Question: {query}\n\nAnswer:")
        prompt = "\n\n".join(prompt_parts)
        instruction = WEB_SYSTEM_INSTRUCTION if is_web_sourced else SYSTEM_INSTRUCTION

        groundedness_feedback = state.get("groundedness_feedback")
        if groundedness_feedback:
            logger.info(f"GenerateNode incorporating groundedness feedback: '{groundedness_feedback}'")
            prompt += (
                f"\n\nIMPORTANT REGENERATION NOTE: A previous draft contained unsupported claims: {groundedness_feedback}. "
                "You must strictly adhere ONLY to facts directly stated in the context passages above and eliminate all ungrounded assertions."
            )

        logger.info(f"GenerateNode invoking LLM gateway for query: '{query}' (web_sourced: {is_web_sourced})")
        answer_text, provider_used = await self.gateway.generate(
            prompt=prompt,
            purpose="generation",
            system_instruction=instruction,
        )

        clean_answer = answer_text.strip()
        if is_web_sourced and not clean_answer.lower().startswith(("[web", "(web", "web-sourced")):
            clean_answer = f"[Web-Sourced Answer]\n{clean_answer}"

        # Cache write-through to Two-Tier Cache (exact SHA-256 + semantic vector index)
        doc_ids = list({c.doc_id for c in chunks})
        try:
            await self.cache_service.async_store(
                query=query,
                access_level=access_level,
                answer=clean_answer,
                citations=[c.model_dump() for c in citations],
                doc_ids=doc_ids,
                trace_id=trace_id,
            )
            logger.info(
                f"GenerateNode stored response in two-tier cache for query: '{query}'"
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to store generated response in cache: {e}")

        return {
            "draft_answer": clean_answer,
            "final_answer": clean_answer,
            "citations": citations,
            "provider_used": provider_used,
        }
