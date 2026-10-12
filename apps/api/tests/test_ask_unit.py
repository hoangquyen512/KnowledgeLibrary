from __future__ import annotations

import asyncio
import re
from uuid import uuid4

from app.rag.providers import (
    MockGeminiProvider,
    parse_notebooklm_answer,
    parse_structured_answer,
    structured_to_markdown,
)
from app.rag.retrieval import validate_citation_indices
from app.rag.types import RetrievalHit
from app.rag.search_tokens import extract_search_tokens


def test_validate_citation_indices() -> None:
    assert validate_citation_indices([1, 2, 2, 99, 0, -1], 3) == [1, 2]
    assert validate_citation_indices([], 5) == []


def test_extract_search_tokens_skips_stopwords() -> None:
    tokens = extract_search_tokens(
        "Tổng hợp các nội dung thay đổi của dự án Đại Tân Việt (DTV)"
    )
    low = {t.lower() for t in tokens}
    assert "dtv" in low
    assert "các" not in low
    assert any("tân" in t.lower() or "việt" in t.lower() or "dai" in t.lower() for t in tokens)


def test_parse_structured_answer_validates_citations() -> None:
    raw = {
        "answer_type": "LIST",
        "summary": ["Point A", "Point B"],
        "key_changes": [
            {"title": "Change 1", "description": "Detail", "citation_indices": [1, 99]},
            {"title": "Change 2", "citation_indices": [2]},
        ],
        "highlights": [{"text": "API detail [1]", "citation_indices": [1]}],
        "compare": None,
        "caveat": None,
        "markdown": None,
    }
    structured, cited = parse_structured_answer(raw, available_count=2)
    assert structured is not None
    assert structured["answer_type"] == "LIST"
    assert structured["key_changes"][0]["citation_indices"] == [1]
    assert 1 in cited and 2 in cited
    assert 99 not in cited


def test_parse_structured_answer_from_fenced_json() -> None:
    raw = """```json
{"answer_type":"SUMMARY","summary":["A complete natural language overview sentence here.","Second overview point for the user."],"key_changes":[{"title":"Topic","description":"","citation_indices":[1]}],"highlights":[],"compare":null,"caveat":null,"markdown":null}
```"""
    structured, cited = parse_structured_answer(raw, available_count=3, question="What changed?")
    assert structured is not None
    assert len(structured["summary"]) >= 2
    assert 1 in cited


def test_mock_summary_natural_vietnamese() -> None:
    hits = [
        RetrievalHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            space_id=uuid4(),
            title="[Enhance] Bổ sung cấu hình Công ty ĐẠI TÂN VIỆT",
            snippet="Trang chủ → DMS → Quản lý profile {{tencuahang}} Giao diện màn hình Popup xác nhận",
            score=2.0,
            chunk_index=0,
        ),
    ]

    async def run() -> None:
        result = await MockGeminiProvider().generate("Tổng hợp thay đổi dự án Đại Tân Việt", hits)
        assert result.structured is not None
        assert result.structured.get("format") == "notebooklm"
        answer = result.structured.get("answer") or ""
        assert "Across" not in answer
        assert "{{" not in answer
        assert "Trang chủ" not in answer
        assert "[1]" in answer

    asyncio.run(run())


def test_finalize_summary_rejects_garbage() -> None:
    from app.rag.providers import finalize_summary

    bad = [
        "Across 4 document(s) and 8 related passage(s), the sources address: [Enhance] foo",
        "Trang chủ → DMS → {{tencuahang}} Giao diện màn hình Popup",
    ]
    kc = [{"title": "Bổ sung cấu hình Đại Tân Việt", "description": "", "citation_indices": [1]}]
    out = finalize_summary(bad, "Tổng hợp thay đổi", kc)
    assert "Tóm lược" in out[0]
    assert "{{" not in " ".join(out)


def test_structured_to_markdown_includes_sections() -> None:
    md = structured_to_markdown(
        {
            "summary": ["One"],
            "key_changes": [{"title": "Alpha", "description": "", "citation_indices": [1]}],
            "highlights": [{"text": "Detail", "citation_indices": [1]}],
        }
    )
    assert "Quick summary" in md
    assert "###" not in md
    assert "Key changes" in md
    assert "Alpha" in md


def test_to_plain_text_strips_markdown() -> None:
    from app.rag.providers import to_plain_text

    assert to_plain_text("### Heading\n**bold** and `code`") == "Heading\nbold and code"
    assert "**" not in to_plain_text("**x**")
    assert "`" not in to_plain_text("`api`")


def test_parse_structured_answer_strips_markdown_in_fields() -> None:
    raw = {
        "answer_type": "LIST",
        "summary": ["**Bold** point with `API`"],
        "key_changes": [
            {"title": "### Title", "description": "*italic*", "citation_indices": [1]},
        ],
        "highlights": [{"text": "Detail [1]", "citation_indices": [1]}],
        "compare": None,
        "caveat": None,
        "markdown": None,
    }
    structured, _cited = parse_structured_answer(raw, available_count=2, question="What changed?")
    assert structured is not None
    assert structured["summary"]
    assert "Bold point with API" in structured["summary"][0] or "main themes" in structured["summary"][0]
    assert structured["key_changes"][0]["title"] == "Title"
    assert structured["key_changes"][0]["description"] == "italic"
    assert "[1]" not in structured["highlights"][0]["text"]


def test_parse_notebooklm_answer_keeps_inline_citations() -> None:
    hits = [
        RetrievalHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            space_id=uuid4(),
            title="Onboarding",
            snippet="Parent enters student code.",
            score=1.0,
            chunk_index=0,
            section_heading="Registration",
            source_url="https://confluence.example/pages/1",
            content="Parent enters student code.",
        ),
    ]
    raw = {
        "answer": "Parents must enter a student code during onboarding. [1]",
        "sources": [
            {
                "id": 1,
                "page_title": "Onboarding",
                "section_heading": "Registration",
                "source_url": "https://confluence.example/pages/1",
                "quoted_snippet": "Parent enters student code.",
            }
        ],
    }
    structured, cited = parse_notebooklm_answer(raw, available_count=1, hits=hits)
    assert structured is not None
    assert "[1]" in structured["answer"]
    assert cited == [1]
    assert structured["sources"][0]["quoted_snippet"]


def test_mock_gemini_cites_sources() -> None:
    hits = [
        RetrievalHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            space_id=uuid4(),
            title="Onboarding",
            snippet="Parent enters student code. Then the system validates the profile before payment.",
            score=2.0,
            chunk_index=0,
        ),
        RetrievalHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            space_id=uuid4(),
            title="Payment",
            snippet="Pay tuition fees through the online checkout after onboarding completes successfully.",
            score=1.0,
            chunk_index=0,
        ),
    ]

    async def run() -> None:
        result = await MockGeminiProvider().generate("How does onboarding work?", hits)
        assert result.provider == "MOCK"
        assert result.cited_indices
        assert all(1 <= i <= len(hits) for i in result.cited_indices)
        assert result.structured is not None
        assert result.structured.get("format") == "notebooklm"
        assert result.structured.get("answer")
        assert "[1]" in result.structured["answer"]
        assert result.structured["sources"]

        empty = await MockGeminiProvider().generate("anything", [])
        assert "không tìm thấy" in empty.text.lower()
        assert empty.cited_indices == []
        assert empty.structured is not None
        assert empty.structured["answer_type"] == "NO_SOURCE"

    asyncio.run(run())


def test_parse_summary_strips_citations_and_keeps_complete_text() -> None:
    raw = {
        "answer_type": "SUMMARY",
        "summary": [
            "The project adds partner profile configuration for Dai Tan Viet. [1]",
            "Order screens gain search and warehouse binding for distributors.",
        ],
        "key_changes": [
            {"title": "Partner config", "description": "Detail", "citation_indices": [1]},
        ],
        "highlights": [],
        "compare": None,
        "caveat": None,
        "markdown": None,
    }
    structured, cited = parse_structured_answer(raw, available_count=2)
    assert structured is not None
    assert "[1]" not in structured["summary"][0]
    assert structured["summary"][0].endswith(".")
    assert 1 in cited
