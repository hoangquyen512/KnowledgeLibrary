"""Unit tests for multi-source parsers and Jira normalizer."""

import io

import pytest

from app.ingestion.parsers import ensure_parsers_loaded, get_parser, list_parsers
from app.jira.normalize import normalize_jira_issue
from app.models.source import SourceType


def test_parser_registry_loads_all_file_types():
    ensure_parsers_loaded()
    registered = set(list_parsers())
    for st in (
        SourceType.FILE_EXCEL,
        SourceType.FILE_CSV,
        SourceType.FILE_WORD,
        SourceType.FILE_POWERPOINT,
        SourceType.FILE_PDF,
    ):
        assert st in registered
        assert get_parser(st).source_type == st


def test_csv_parser_basic():
    ensure_parsers_loaded()
    data = "ID,Name,Status\n1,Alpha,Done\n2,Beta,Open\n".encode("utf-8")
    result = get_parser(SourceType.FILE_CSV).parse(data, filename="mapping.csv")
    assert result.error_code is None
    assert len(result.documents) == 1
    doc = result.documents[0]
    assert "Alpha" in doc.normalized_text
    assert doc.chunk_hints
    assert "Rows" in (doc.chunk_hints[0].metadata.get("citation_label") or "")
    assert result.preview["total_rows"] == 2


def test_excel_parser_sheet_selection(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "CR"
    ws1.append(["ID", "Feature"])
    ws1.append(["CR001", "Price API"])
    ws2 = wb.create_sheet("SkipMe")
    ws2.append(["A"])
    ws2.append(["1"])
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    ensure_parsers_loaded()
    parser = get_parser(SourceType.FILE_EXCEL)
    preview = parser.parse(data, filename="Change_Request.xlsx")
    assert preview.error_code is None
    assert len(preview.documents) == 2

    selected = parser.parse(
        data, filename="Change_Request.xlsx", options={"sheet_names": ["CR"]}
    )
    assert len(selected.documents) == 1
    assert selected.documents[0].title == "Sheet: CR"
    assert "Price API" in selected.documents[0].normalized_text
    cite = selected.documents[0].chunk_hints[0].metadata.get("citation_label")
    assert "Sheet CR" in cite


def test_docx_parser_headings():
    pytest.importorskip("docx")
    try:
        from docx import Document as DocxDocument
    except ImportError:
        pytest.skip("python-docx required (remove conflicting `docx` package if present)")

    doc = DocxDocument()
    doc.add_heading("Business Rules", level=1)
    doc.add_paragraph("Promotion rules apply to all SKUs.")
    doc.add_heading("Eligibility", level=2)
    doc.add_paragraph("Only VIP customers.")
    buf = io.BytesIO()
    doc.save(buf)

    ensure_parsers_loaded()
    result = get_parser(SourceType.FILE_WORD).parse(buf.getvalue(), filename="Business_Rules.docx")
    assert result.error_code is None
    assert len(result.documents) == 1
    assert result.documents[0].chunk_hints
    labels = [c.metadata.get("citation_label") for c in result.documents[0].chunk_hints]
    assert any("Business_Rules.docx" in (l or "") for l in labels)


def test_pptx_parser_slides():
    pytest.importorskip("pptx")
    from pptx import Presentation

    prs = Presentation()
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Project Overview"
    slide.placeholders[1].text = "Phase 1 complete"
    buf = io.BytesIO()
    prs.save(buf)

    ensure_parsers_loaded()
    result = get_parser(SourceType.FILE_POWERPOINT).parse(
        buf.getvalue(), filename="Project_Update.pptx"
    )
    assert result.error_code is None
    assert result.documents[0].chunk_hints
    cite = result.documents[0].chunk_hints[0].metadata.get("citation_label")
    assert "Slide" in (cite or "")


def test_pdf_parser_text_pages():
    # Minimal PDF with text via reportlab if available; else pypdf blank → OCR_REQUIRED
    try:
        import fitz
    except ImportError:
        pytest.skip("pymupdf not installed")
    if not hasattr(fitz, "open"):
        pytest.skip("pymupdf broken or shadowed — reinstall pymupdf in venv")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Requirement Spec page content")
    data = doc.tobytes()
    doc.close()

    ensure_parsers_loaded()
    result = get_parser(SourceType.FILE_PDF).parse(data, filename="Requirement_Spec.pdf")
    assert result.error_code is None
    assert result.documents
    cite = result.documents[0].chunk_hints[0].metadata.get("citation_label")
    assert "Page 1" in (cite or "")


def test_jira_normalizer_citation():
    issue = {
        "id": "10001",
        "key": "ECOM-123",
        "fields": {
            "summary": "Đồng bộ đơn hàng TikTok",
            "description": "Sync TikTok orders daily.",
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Story"},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "labels": ["ecom"],
            "components": [{"name": "Order"}],
            "created": "2026-01-01T00:00:00.000+0000",
            "updated": "2026-01-02T00:00:00.000+0000",
            "comment": {
                "comments": [
                    {"author": {"displayName": "Alice"}, "body": "Working on it."}
                ]
            },
        },
    }
    nd = normalize_jira_issue(
        issue,
        base_url="https://jira.example.com",
        include={"description": True, "comments": True, "acceptance_criteria": True},
    )
    assert nd.source_locator == "ECOM-123"
    assert "Issue Key: ECOM-123" in nd.normalized_text
    assert "Description:" in nd.normalized_text
    assert nd.chunk_hints
    assert nd.chunk_hints[0].metadata["citation_label"].startswith("ECOM-123")
    assert nd.external_url.endswith("/browse/ECOM-123")


def test_file_validate_rejects_exe():
    from fastapi import HTTPException

    from app.ingestion.file_validate import validate_upload

    with pytest.raises(HTTPException) as exc:
        validate_upload(
            filename="malware.exe",
            content_type="application/octet-stream",
            data=b"MZ" + b"\x00" * 100,
        )
    assert exc.value.detail["code"] == "UNSUPPORTED_FILE_TYPE"
