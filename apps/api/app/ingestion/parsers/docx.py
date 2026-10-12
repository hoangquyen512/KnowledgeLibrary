"""Word (.docx) parser — preserve heading hierarchy in one document."""

from __future__ import annotations

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


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    name = style_name.strip().lower()
    for i in range(1, 10):
        if name == f"heading {i}" or name.startswith(f"heading {i}"):
            return i
    return None


class DocxParser:
    source_type = SourceType.FILE_WORD

    def parse(
        self, data: bytes, *, filename: str, options: dict[str, Any] | None = None
    ) -> ParseResult:
        try:
            from docx import Document as DocxDocument
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            import io

            doc = DocxDocument(io.BytesIO(data))
            sections: list[NormalizedSection] = []
            chunks: list[ChunkHint] = []
            path: list[str] = []
            current_title = "Introduction"
            current_parts: list[str] = []
            all_lines: list[str] = []
            link_count = 0
            image_count = 0

            def flush() -> None:
                nonlocal current_parts, current_title
                text = "\n".join(p for p in current_parts if p.strip()).strip()
                if not text:
                    current_parts = []
                    return
                heading_path = " > ".join(path) if path else current_title
                sections.append(NormalizedSection(title=current_title, text=text))
                chunks.append(
                    ChunkHint(
                        text=f"{heading_path}\n\n{text}",
                        position=len(chunks),
                        metadata={
                            "heading_path": heading_path,
                            "citation_label": f"{filename} — {current_title}",
                        },
                    )
                )
                current_parts = []

            for block in doc.element.body:
                tag = block.tag.split("}")[-1]
                if tag == "p":
                    para = Paragraph(block, doc)
                    level = _heading_level(para.style.name if para.style else None)
                    text = (para.text or "").strip()
                    # hyperlinks count
                    if "hyperlink" in para._element.xml:  # noqa: SLF001
                        link_count += 1
                    if level is not None:
                        flush()
                        path = path[: level - 1]
                        path.append(text or f"Heading {level}")
                        current_title = text or f"Heading {level}"
                        all_lines.append("#" * min(level, 6) + f" {current_title}")
                    elif text:
                        current_parts.append(text)
                        all_lines.append(text)
                elif tag == "tbl":
                    table = Table(block, doc)
                    rows_text: list[str] = []
                    for row in table.rows:
                        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                        rows_text.append(" | ".join(cells))
                    if rows_text:
                        table_block = "Table:\n" + "\n".join(rows_text)
                        current_parts.append(table_block)
                        all_lines.append(table_block)

            for rel in doc.part.rels.values():
                if "image" in rel.reltype:
                    image_count += 1

            flush()
            if not sections:
                # fallback: entire body as one section
                body = "\n".join(all_lines).strip() or "(empty document)"
                sections = [NormalizedSection(title=filename, text=body)]
                chunks = [
                    ChunkHint(
                        text=body,
                        position=0,
                        metadata={
                            "heading_path": filename,
                            "citation_label": filename,
                        },
                    )
                ]

            full_text = "\n\n".join(
                f"## {s.title}\n{s.text}" if s.title else s.text for s in sections
            )
            title = filename.rsplit(".", 1)[0] or filename
            # Prefer first H1
            for s in sections:
                if s.title and s.title != "Introduction":
                    title = s.title
                    break

            return ParseResult(
                documents=[
                    NormalizedDocument(
                        title=title,
                        document_type=DocumentType.FILE,
                        source_type=SourceType.FILE_WORD,
                        source_locator=filename,
                        normalized_text=full_text,
                        external_id=f"docx:{filename}",
                        sections=sections,
                        chunk_hints=chunks,
                        raw_metadata={
                            "filename": filename,
                            "section_count": len(sections),
                            "hyperlink_count": link_count,
                            "image_count": image_count,
                        },
                    )
                ],
                preview={
                    "filename": filename,
                    "title": title,
                    "section_count": len(sections),
                    "image_count": image_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ParseResult(
                documents=[],
                error_code="DOCX_PARSE_FAILED",
                error_message=str(exc)[:500],
            )


register_parser(DocxParser())
