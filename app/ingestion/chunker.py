"""Text chunker with configurable size, overlap, and boundary awareness."""

from datetime import UTC, datetime

from app.ingestion.loaders import RawDocumentPart
from app.ingestion.models import ChunkPayload


class SemanticChunker:
    """Recursive boundary-aware chunker that splits text while preserving sections and pages."""

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
            "; ",
            ", ",
            " ",
            "",
        ]

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using the first matching separator."""
        final_chunks: list[str] = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1 :]
                break

        splits = text.split(separator) if separator != "" else list(text)

        good_splits: list[str] = []
        for s in splits:
            if not s:
                continue
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if new_separators:
                    other_splits = self._split_text(s, new_separators)
                    good_splits.extend(other_splits)
                else:
                    good_splits.append(s)

        # Merge splits up to chunk_size respecting chunk_overlap
        if not good_splits:
            return []

        merged_chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for piece in good_splits:
            piece_len = len(piece) + (len(separator) if current_chunk else 0)
            if current_len + piece_len <= self.chunk_size:
                current_chunk.append(piece)
                current_len += piece_len
            else:
                if current_chunk:
                    joined = separator.join(current_chunk).strip()
                    if joined:
                        merged_chunks.append(joined)
                    # Create overlap from end of current_chunk
                    overlap_chunk: list[str] = []
                    overlap_len = 0
                    for prev_piece in reversed(current_chunk):
                        if overlap_len + len(prev_piece) <= self.chunk_overlap:
                            overlap_chunk.insert(0, prev_piece)
                            overlap_len += len(prev_piece)
                        else:
                            break
                    current_chunk = overlap_chunk
                    current_len = overlap_len
                current_chunk.append(piece)
                current_len += len(piece)

        if current_chunk:
            joined = separator.join(current_chunk).strip()
            if joined:
                merged_chunks.append(joined)

        return merged_chunks

    def chunk_document(
        self,
        raw_parts: list[RawDocumentPart],
        doc_id: str,
        source: str,
        source_type: str,
        access_level: str = "default",
        doc_version: int = 1,
    ) -> list[ChunkPayload]:
        """Convert extracted parts of a document into a sequence of ChunkPayloads."""
        chunks: list[ChunkPayload] = []
        chunk_idx = 0
        now = datetime.now(UTC)

        for part in raw_parts:
            text = part.content.strip()
            if not text:
                continue

            sub_chunks = self._split_text(text, self.separators)
            for sub_text in sub_chunks:
                clean_text = sub_text.strip()
                if not clean_text:
                    continue

                chunk = ChunkPayload(
                    doc_id=doc_id,
                    doc_version=doc_version,
                    source=source,
                    source_type=source_type,  # type: ignore
                    modality="text",
                    section=part.section,
                    page=part.page,
                    chunk_index=chunk_idx,
                    access_level=access_level,
                    ingested_at=now,
                    content=clean_text,
                )
                chunks.append(chunk)
                chunk_idx += 1

        return chunks
