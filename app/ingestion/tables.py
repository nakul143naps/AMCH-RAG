"""Table serialization to Markdown and tabular region processing."""

import logging
import re

logger = logging.getLogger(__name__)


def serialize_rows_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    """Serialize a list of column headers and data rows to a GitHub-flavored Markdown table.

    Example output:
    | Year | Revenue | Growth |
    | --- | --- | --- |
    | 2023 | $10M | +15% |
    """
    if not headers and not rows:
        return ""

    # Normalize column count
    num_cols = max(len(headers), max((len(r) for r in rows), default=0))
    if num_cols == 0:
        return ""

    norm_headers = [str(h).strip().replace("\n", " ") for h in headers]
    if len(norm_headers) < num_cols:
        norm_headers.extend([f"Column {i + 1}" for i in range(len(norm_headers), num_cols)])

    separator = ["---"] * num_cols

    markdown_lines = [
        "| " + " | ".join(norm_headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in rows:
        norm_row = [str(cell).strip().replace("\n", " ") for cell in row]
        if len(norm_row) < num_cols:
            norm_row.extend([""] * (num_cols - len(norm_row)))
        elif len(norm_row) > num_cols:
            norm_row = norm_row[:num_cols]
        markdown_lines.append("| " + " | ".join(norm_row) + " |")

    return "\n".join(markdown_lines)


def format_table_as_markdown(grid: list[list[str]]) -> str:
    """Convert a 2D matrix of table cells into a Markdown table, treating row 0 as headers."""
    if not grid:
        return ""
    headers = grid[0]
    data_rows = grid[1:] if len(grid) > 1 else []
    return serialize_rows_to_markdown(headers, data_rows)


def detect_and_format_text_table(text: str) -> str | None:
    """Detect if a block of plain text is a pipe-delimited or whitespace-aligned table and format it."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    # Check for pipe-delimited tables
    if all("|" in line for line in lines):
        parsed_rows = []
        for line in lines:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                parsed_rows.append(cells)
        if len(parsed_rows) >= 2:
            return format_table_as_markdown(parsed_rows)

    # Check for tab or multi-space delimited columns
    split_rows = [re.split(r"\t+|\s{2,}", line) for line in lines]
    col_counts = [len(r) for r in split_rows]
    if len(set(col_counts)) == 1 and col_counts[0] >= 2:
        return format_table_as_markdown(split_rows)

    return None
