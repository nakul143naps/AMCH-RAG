"""Document loaders for TXT, Markdown, PDF, and DOCX files."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import docx
import pypdf


class RawDocumentPart:
    """Represents a discrete part of an extracted document (e.g., page, section)."""

    def __init__(
        self,
        content: str,
        page: int | None = None,
        section: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.content = content.strip()
        self.page = page
        self.section = section
        self.metadata = metadata or {}


class BaseDocumentLoader(ABC):
    """Abstract base class for file document loaders."""

    @abstractmethod
    def load(self, file_path: str | Path) -> list[RawDocumentPart]:
        """Extract structured parts from the given document file."""


class TextLoader(BaseDocumentLoader):
    """Loader for plain text (.txt) files."""

    def load(self, file_path: str | Path) -> list[RawDocumentPart]:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        if not text.strip():
            return []
        return [RawDocumentPart(content=text, page=1)]


class MarkdownLoader(BaseDocumentLoader):
    """Loader for Markdown (.md) files, preserving section hierarchy where possible."""

    def load(self, file_path: str | Path) -> list[RawDocumentPart]:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        if not text.strip():
            return []

        # Split by top-level headers (# or ##) if present, otherwise single part
        lines = text.splitlines()
        parts: list[RawDocumentPart] = []
        current_section: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if line.startswith("# ") or line.startswith("## "):
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        parts.append(
                            RawDocumentPart(
                                content=content, section=current_section, page=1
                            )
                        )
                    current_lines = []
                current_section = line.lstrip("#").strip()
            current_lines.append(line)

        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                parts.append(
                    RawDocumentPart(content=content, section=current_section, page=1)
                )

        return parts if parts else [RawDocumentPart(content=text, page=1)]


class PDFLoader(BaseDocumentLoader):
    """Loader for PDF documents extracting text page by page using pypdf."""

    def load(self, file_path: str | Path) -> list[RawDocumentPart]:
        path = Path(file_path)
        parts: list[RawDocumentPart] = []

        reader = pypdf.PdfReader(str(path))
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(RawDocumentPart(content=text, page=idx))

        return parts


class DocxLoader(BaseDocumentLoader):
    """Loader for DOCX files extracting text and table data using python-docx."""

    def load(self, file_path: str | Path) -> list[RawDocumentPart]:
        path = Path(file_path)
        doc = docx.Document(str(path))
        parts: list[RawDocumentPart] = []

        # Paragraphs
        lines = []
        for p in doc.paragraphs:
            if p.text.strip():
                lines.append(p.text)

        # Tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(" | ".join(cells))
            if table_rows:
                lines.append("\n" + "\n".join(table_rows))

        combined = "\n\n".join(lines).strip()
        if combined:
            parts.append(RawDocumentPart(content=combined, page=1))

        return parts


def get_loader_for_file(file_path: str | Path) -> BaseDocumentLoader:
    """Factory to retrieve appropriate document loader by file extension."""
    ext = Path(file_path).suffix.lower()
    loaders: dict[str, BaseDocumentLoader] = {
        ".txt": TextLoader(),
        ".md": MarkdownLoader(),
        ".pdf": PDFLoader(),
        ".docx": DocxLoader(),
    }
    loader = loaders.get(ext)
    if not loader:
        raise ValueError(
            f"Unsupported file extension: {ext}. Supported: {list(loaders.keys())}"
        )
    return loader
