from __future__ import annotations

from uuid import uuid4

from app.studio.pack import PackedSource, estimate_chars, snippet_from_content
from app.studio.parse import parse_mindmap, parse_presentation
from app.studio.prompts import mindmap_prompt, presentation_prompt, user_focus_block


def _source(idx: int = 1) -> PackedSource:
    return PackedSource(
        index=idx,
        document_id=uuid4(),
        chunk_id=uuid4(),
        space_id=uuid4(),
        title="Policy Guide",
        content="Refund rules apply within 30 days for eligible orders.",
        section_heading="Returns",
        source_url="https://example.com/page",
        snippet="Refund rules apply",
    )


def test_parse_presentation_clamps_bullets_and_refs() -> None:
    sources = [_source(1), _source(2)]
    sources[1].index = 2
    raw = {
        "title": "Returns Overview",
        "slides": [
            {
                "title": "Context",
                "bullets": [f"Point {i}" for i in range(10)],
                "notes": "Explain briefly",
                "source_indices": [1, 99],
            }
        ],
    }
    parsed = parse_presentation(raw, sources)
    assert parsed is not None
    assert parsed["title"] == "Returns Overview"
    slide = parsed["slides"][0]
    assert len(slide["bullets"]) <= 6
    assert len(slide["source_refs"]) == 1
    assert slide["source_refs"][0]["title"] == "Policy Guide"


def test_parse_mindmap_enforces_depth_and_root() -> None:
    sources = [_source()]
    raw = {
        "root_label": "Returns",
        "nodes": [
            {"id": "root", "label": "Returns", "parent_id": None, "source_index": 1},
            {"id": "n1", "label": "Window", "parent_id": "root", "source_index": 1},
            {"id": "n2", "label": "Too deep", "parent_id": "n1", "source_index": 1},
        ],
    }
    parsed = parse_mindmap(raw, sources)
    assert parsed is not None
    ids = {n["id"] for n in parsed["nodes"]}
    assert "root" in ids
    assert "n1" in ids


def test_estimate_chars_and_snippet() -> None:
    src = _source()
    assert estimate_chars([src]) > 0
    long = "word " * 200
    assert len(snippet_from_content(long)) <= 241


def test_user_focus_block_empty_when_blank() -> None:
    assert user_focus_block(None) == ""
    assert user_focus_block("   ") == ""


def test_prompts_include_focus_for_presentation_and_mindmap() -> None:
    focus = "quy trình đối soát thu tiền"
    pres = presentation_prompt("Context here", focus_prompt=focus)
    mind = mindmap_prompt("Context here", focus_prompt=focus)
    assert focus in pres
    assert focus in mind
    assert "Người dùng yêu cầu tập trung vào" in pres
    assert "Người dùng yêu cầu tập trung vào" in mind
    assert user_focus_block(focus) not in presentation_prompt("ctx", focus_prompt=None)
