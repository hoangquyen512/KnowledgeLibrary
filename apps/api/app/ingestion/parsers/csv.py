"""CSV parser with encoding / delimiter detection."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.ingestion.parsers import (
    ChunkHint,
    NormalizedDocument,
    NormalizedSection,
    ParseResult,
    register_parser,
)
from app.models.document import DocumentType
from app.models.source import SourceType

_ROWS_PER_CHUNK = 50
_PREVIEW_ROWS = 20


def _decode(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


class CsvParser:
    source_type = SourceType.FILE_CSV

    def parse(
        self, data: bytes, *, filename: str, options: dict[str, Any] | None = None
    ) -> ParseResult:
        options = options or {}
        try:
            text, encoding = _decode(data)
            delimiter = options.get("delimiter") or _detect_delimiter(text)
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return ParseResult(
                    documents=[],
                    error_code="CSV_PARSE_FAILED",
                    error_message="CSV file is empty.",
                )
            headers = [h.strip() or f"Column{i+1}" for i, h in enumerate(rows[0])]
            data_rows = [r for r in rows[1:] if any(cell.strip() for cell in r)]
            # normalize width
            normalized: list[list[str]] = []
            for row in data_rows:
                cells = [c.strip() for c in row]
                if len(cells) < len(headers):
                    cells.extend([""] * (len(headers) - len(cells)))
                normalized.append(cells[: len(headers)])

            header_line = "Columns: " + " | ".join(headers)
            body = [f"File: {filename}", header_line, ""]
            for i, row in enumerate(normalized, start=1):
                body.append(f"Row {i}: " + " | ".join(row))
            full_text = "\n".join(body)

            chunks: list[ChunkHint] = []
            for start in range(0, max(len(normalized), 1), _ROWS_PER_CHUNK):
                batch = normalized[start : start + _ROWS_PER_CHUNK]
                if not batch and start > 0:
                    break
                row_start = start + 1
                row_end = start + len(batch)
                lines = [f"File: {filename}", header_line, f"Rows {row_start}–{row_end}", ""]
                lines.append(" | ".join(headers))
                for row in batch:
                    lines.append(" | ".join(row))
                chunks.append(
                    ChunkHint(
                        text="\n".join(lines),
                        position=len(chunks),
                        metadata={
                            "row_start": row_start,
                            "row_end": row_end,
                            "citation_label": f"{filename} — Rows {row_start}–{row_end}",
                        },
                    )
                )

            doc = NormalizedDocument(
                title=filename.rsplit(".", 1)[0] or filename,
                document_type=DocumentType.SHEET,
                source_type=SourceType.FILE_CSV,
                source_locator=filename,
                normalized_text=full_text,
                external_id=f"csv:{filename}",
                sections=[NormalizedSection(title="CSV", text=full_text)],
                chunk_hints=chunks,
                raw_metadata={
                    "filename": filename,
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "row_count": len(normalized),
                    "column_count": len(headers),
                    "headers": headers,
                },
            )
            preview_rows = [dict(zip(headers, row, strict=False)) for row in normalized[:_PREVIEW_ROWS]]
            return ParseResult(
                documents=[doc],
                preview={
                    "filename": filename,
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "columns": headers,
                    "total_rows": len(normalized),
                    "preview_rows": preview_rows,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ParseResult(
                documents=[],
                error_code="CSV_PARSE_FAILED",
                error_message=str(exc)[:500],
            )


register_parser(CsvParser())
