"""Tests for semantic and recursive boundary-aware chunking."""

from app.ingestion.chunker import SemanticChunker
from app.ingestion.loaders import RawDocumentPart


def test_chunker_basic():
    chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
    text = (
        "Agentic RAG represents the next generation of Retrieval Augmented Generation. "
        "It uses intelligent decision routing and iterative loops to ensure grounded responses. "
        "Corrective RAG specifically evaluates the quality of retrieved contexts and rewrites queries if needed."
    )
    part = RawDocumentPart(content=text, page=1, section="Intro")
    chunks = chunker.chunk_document(
        raw_parts=[part],
        doc_id="test_doc",
        source="test.txt",
        source_type="txt",
    )

    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.doc_id == "test_doc"
        assert c.section == "Intro"
        assert c.page == 1
        assert len(c.content) <= 150  # Boundary buffer


def test_chunker_empty_input():
    chunker = SemanticChunker()
    chunks = chunker.chunk_document(
        raw_parts=[],
        doc_id="empty_doc",
        source="empty.txt",
        source_type="txt",
    )
    assert chunks == []
