"""High-level document summarizer for hierarchical cataloging and summary-guided routing."""

import asyncio
import logging
import re
from typing import Any

from app.cache.manager import CacheManager
from app.gateway.client import ModelGateway
from app.retrieval.models import RetrievedChunk
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

SUMMARIZER_SYSTEM_INSTRUCTION = """You are an expert document cataloger and technical summarizer.
Analyze the provided document title, sections, table of contents, and content excerpts.
Generate a concise, high-level summary and topic index so an intelligent routing agent can determine which questions can be answered using this document.

Format your output EXACTLY as:
TOPICS: <comma-separated list of all major topics, chapters, roadmap clusters, sections, key algorithms, and concepts covered>
SUMMARY: <concise 2-3 sentence executive summary explaining what this document is about and what specific questions or skills it answers>"""


class DocumentSummarizer:
    """Extracts and caches high-level document summaries for summary-guided query routing."""

    _instance: Any = None

    @classmethod
    def get_instance(cls) -> "DocumentSummarizer":
        if cls._instance is None:
            cls._instance = DocumentSummarizer()
        return cls._instance

    def __init__(
        self,
        cache_mgr: CacheManager | None = None,
        gateway: ModelGateway | None = None,
        vector_mgr: VectorStoreManager | None = None,
    ) -> None:
        self.cache_mgr = cache_mgr or CacheManager.get_instance()
        self.gateway = gateway or ModelGateway.get_instance()
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()

    def generate_heuristic_summary(
        self,
        source_name: str,
        sections: list[str],
        sample_texts: list[str],
    ) -> tuple[str, str]:
        """Generate a deterministic fallback summary if LLM call fails or during unit tests."""
        clean_sections = [s.strip() for s in sections if s and len(s.strip()) > 2]
        topics = ", ".join(clean_sections[:15]) if clean_sections else source_name
        
        extracted_topics: list[str] = list(clean_sections)
        for text in sample_texts:
            for line in text.splitlines():
                line = line.strip()
                if any(line.lower().startswith(prefix) for prefix in ["cluster", "chapter", "section", "part", "module", "roadmap"]):
                    extracted_topics.append(line)
        
        if extracted_topics:
            topics = ", ".join(dict.fromkeys(extracted_topics))[:300]
        
        summary = (
            f"Uploaded document '{source_name}' containing {len(sections)} sections and content covering: {topics[:200]}."
        )
        return summary, topics

    async def summarize_document(
        self,
        doc_id: str,
        source_name: str,
        chunks: list[Any],
    ) -> dict[str, str]:
        """Generate high-level summary and topics for a document, then store in cache."""
        if not chunks:
            summary, topics = self.generate_heuristic_summary(source_name, [], [])
            self.cache_mgr.set_document_summary(doc_id, source_name, summary, topics)
            return {"summary": summary, "topics": topics}

        # Collect sections, cluster names, and content samples across chunks
        sections: list[str] = []
        sample_texts: list[str] = []

        for i, c in enumerate(chunks):
            sec = getattr(c, "section", None)
            if sec and sec not in sections:
                sections.append(sec)
            content = getattr(c, "content", "") or ""
            # Capture beginning chunks (first 3) and periodic samples
            if i < 3 or (i % 5 == 0 and len(sample_texts) < 8):
                if content.strip():
                    sample_texts.append(content[:400])

        combined_context = (
            f"Document Source: {source_name}\n"
            f"Identified Sections/Headers: {', '.join(sections[:25])}\n\n"
            f"Beginning Excerpts & Table of Contents:\n"
            + "\n---\n".join(sample_texts[:5])
        )

        prompt = (
            f"Analyze this document and produce a comprehensive high-level summary and topic list:\n\n"
            f"{combined_context}\n\n"
            "Produce the TOPICS and SUMMARY fields:"
        )

        try:
            response_text, _provider = await self.gateway.generate(
                prompt=prompt,
                purpose="summarization",
                system_instruction=SUMMARIZER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )

            topics_match = re.search(r"TOPICS:\s*(.+)", response_text, re.IGNORECASE)
            summary_match = re.search(r"SUMMARY:\s*(.+)", response_text, re.IGNORECASE | re.DOTALL)

            topics = topics_match.group(1).strip() if topics_match else ", ".join(sections[:15]) or source_name
            summary = summary_match.group(1).strip() if summary_match else f"Comprehensive guide covering {topics[:150]}"

            # Clean formatting
            topics = re.sub(r"\s+", " ", topics).strip()
            summary = re.sub(r"\s+", " ", summary).strip()

            logger.info(f"Generated high-level summary for '{source_name}' via {_provider}")
            self.cache_mgr.set_document_summary(doc_id, source_name, summary, topics)
            return {"summary": summary, "topics": topics}

        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM summarization failed for '{source_name}': {e}. Using heuristic summary.")
            summary, topics = self.generate_heuristic_summary(source_name, sections, sample_texts)
            self.cache_mgr.set_document_summary(doc_id, source_name, summary, topics)
            return {"summary": summary, "topics": topics}

    async def ensure_all_documents_summarized(self) -> None:
        """Inspect all documents in Qdrant; if any missing from SQLite summary cache, summarize them."""
        from app.config import get_settings

        settings = get_settings()
        try:
            points, _ = self.vector_mgr.client.scroll(
                collection_name=settings.QDRANT_COLLECTION,
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )

            # Group chunks by doc_id
            doc_chunks: dict[str, list[RetrievedChunk]] = {}
            doc_names: dict[str, str] = {}
            for pt in points:
                if not pt.payload:
                    continue
                d_id = pt.payload.get("doc_id")
                if not d_id:
                    continue
                if d_id not in doc_chunks:
                    doc_chunks[d_id] = []
                    doc_names[d_id] = pt.payload.get("source", d_id)
                chunk = RetrievedChunk(
                    chunk_id=str(pt.id),
                    score=1.0,
                    content=pt.payload.get("content", ""),
                    doc_id=d_id,
                    source=doc_names[d_id],
                    source_type=pt.payload.get("source_type", "txt"),
                    section=pt.payload.get("section"),
                    page=pt.payload.get("page"),
                )
                doc_chunks[d_id].append(chunk)

            # Clean stale summaries that no longer exist in Qdrant
            with self.cache_mgr.sqlite_cache._get_conn() as conn:
                active_ids = list(doc_chunks.keys())
                if active_ids:
                    placeholders = ",".join("?" for _ in active_ids)
                    conn.execute(
                        f"DELETE FROM document_summaries WHERE doc_id NOT IN ({placeholders})",
                        active_ids,
                    )
                else:
                    conn.execute("DELETE FROM document_summaries")
                conn.commit()

            cached_summaries = {
                s["doc_id"]: s for s in self.cache_mgr.get_all_document_summaries()
            }

            for d_id, chunks in doc_chunks.items():
                if d_id not in cached_summaries:
                    src_name = doc_names.get(d_id, "Untitled")
                    logger.info(
                        f"Generating summary for document: '{src_name}' ({d_id}, {len(chunks)} chunks)"
                    )
                    await self.summarize_document(d_id, src_name, chunks)

        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not ensure document summaries: {e}")
