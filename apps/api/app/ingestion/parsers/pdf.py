"""PDF text extractor. Marks OCR_REQUIRED for image-only pages."""

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


class PdfParser:
    source_type = SourceType.FILE_PDF

    def parse(
        self, data: bytes, *, filename: str, options: dict[str, Any] | None = None
    ) -> ParseResult:
        try:
            return self._parse_pymupdf(data, filename=filename)
        except ImportError:
            try:
                return self._parse_pypdf(data, filename=filename)
            except Exception as exc:  # noqa: BLE001
                return ParseResult(
                    documents=[],
                    error_code="PDF_PARSE_FAILED",
                    error_message=str(exc)[:500],
                )
        except Exception as exc:  # noqa: BLE001
            return ParseResult(
                documents=[],
                error_code="PDF_PARSE_FAILED",
                error_message=str(exc)[:500],
            )

    def _parse_pymupdf(self, data: bytes, *, filename: str) -> ParseResult:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        sections: list[NormalizedSection] = []
        chunks: list[ChunkHint] = []
        pages_with_text = 0
        pages_empty = 0
        all_parts: list[str] = []

        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = (page.get_text("text") or "").strip()
            page_no = i + 1
            if text:
                pages_with_text += 1
                block = f"Page {page_no}\n\n{text}"
                all_parts.append(block)
                sections.append(NormalizedSection(title=f"Page {page_no}", text=text))
                chunks.append(
                    ChunkHint(
                        text=block,
                        position=len(chunks),
                        metadata={
                            "page_number": page_no,
                            "citation_label": f"{filename} — Page {page_no}",
                        },
                    )
                )
            else:
                pages_empty += 1

        doc.close()
        return self._finalize(
            filename=filename,
            sections=sections,
            chunks=chunks,
            all_parts=all_parts,
            page_count=len(sections) + pages_empty,
            pages_with_text=pages_with_text,
            pages_empty=pages_empty,
        )

    def _parse_pypdf(self, data: bytes, *, filename: str) -> ParseResult:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        sections: list[NormalizedSection] = []
        chunks: list[ChunkHint] = []
        all_parts: list[str] = []
        pages_with_text = 0
        pages_empty = 0

        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            page_no = i + 1
            if text:
                pages_with_text += 1
                block = f"Page {page_no}\n\n{text}"
                all_parts.append(block)
                sections.append(NormalizedSection(title=f"Page {page_no}", text=text))
                chunks.append(
                    ChunkHint(
                        text=block,
                        position=len(chunks),
                        metadata={
                            "page_number": page_no,
                            "citation_label": f"{filename} — Page {page_no}",
                        },
                    )
                )
            else:
                pages_empty += 1

        return self._finalize(
            filename=filename,
            sections=sections,
            chunks=chunks,
            all_parts=all_parts,
            page_count=len(reader.pages),
            pages_with_text=pages_with_text,
            pages_empty=pages_empty,
        )

    def _finalize(
        self,
        *,
        filename: str,
        sections: list[NormalizedSection],
        chunks: list[ChunkHint],
        all_parts: list[str],
        page_count: int,
        pages_with_text: int,
        pages_empty: int,
    ) -> ParseResult:
        if pages_with_text == 0 and page_count > 0:
            return ParseResult(
                documents=[],
                preview={
                    "filename": filename,
                    "page_count": page_count,
                    "ocr_required": True,
                },
                error_code="OCR_REQUIRED",
                error_message="This PDF appears to be scanned. OCR is not available yet.",
            )

        title = filename.rsplit(".", 1)[0] or filename
        warnings: list[str] = []
        if pages_empty > 0:
            warnings.append(f"{pages_empty} page(s) had no extractable text.")

        return ParseResult(
            documents=[
                NormalizedDocument(
                    title=title,
                    document_type=DocumentType.FILE,
                    source_type=SourceType.FILE_PDF,
                    source_locator=filename,
                    normalized_text="\n\n".join(all_parts),
                    external_id=f"pdf:{filename}",
                    sections=sections,
                    chunk_hints=chunks,
                    raw_metadata={
                        "filename": filename,
                        "page_count": page_count,
                        "pages_with_text": pages_with_text,
                        "pages_empty": pages_empty,
                    },
                )
            ],
            preview={
                "filename": filename,
                "title": title,
                "page_count": page_count,
                "pages_with_text": pages_with_text,
            },
            warnings=warnings,
        )


register_parser(PdfParser())
