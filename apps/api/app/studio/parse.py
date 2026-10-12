from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from app.studio.pack import (
    MAX_BULLETS_PER_SLIDE,
    MAX_MINDMAP_DEPTH,
    PackedSource,
    snippet_from_content,
)


def _parse_json_text(text: str) -> dict[str, Any] | None:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _source_ref_from_index(idx: int, sources: list[PackedSource]) -> dict[str, Any] | None:
    if idx < 1 or idx > len(sources):
        return None
    src = sources[idx - 1]
    return {
        "document_id": str(src.document_id),
        "chunk_id": str(src.chunk_id) if src.chunk_id else None,
        "title": src.title[:300],
        "snippet": src.snippet or snippet_from_content(src.content),
        "section_heading": src.section_heading[:500] if src.section_heading else None,
        "source_url": src.source_url,
        "space_id": str(src.space_id),
    }


def parse_presentation(
    raw: str | dict[str, Any],
    sources: list[PackedSource],
) -> dict[str, Any] | None:
    data = raw if isinstance(raw, dict) else _parse_json_text(str(raw))
    if not data or not isinstance(data.get("slides"), list):
        return None

    slides: list[dict[str, Any]] = []
    for row in data["slides"]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        bullets_raw = row.get("bullets") or []
        bullets = [str(b).strip() for b in bullets_raw if str(b).strip()][:MAX_BULLETS_PER_SLIDE]
        notes = str(row.get("notes") or "").strip() or None
        indices = row.get("source_indices") or []
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for idx_raw in indices:
            try:
                idx = int(idx_raw)
            except (TypeError, ValueError):
                continue
            ref = _source_ref_from_index(idx, sources)
            if ref and ref["document_id"] not in seen:
                seen.add(ref["document_id"])
                refs.append(ref)
        if not refs and sources:
            ref = _source_ref_from_index(1, sources)
            if ref:
                refs.append(ref)
        slides.append(
            {
                "id": str(uuid4()),
                "title": title[:200],
                "bullets": bullets,
                "notes": notes,
                "source_refs": refs,
            }
        )

    if not slides:
        return None
    deck_title = str(data.get("title") or slides[0]["title"]).strip()[:255]
    return {"title": deck_title, "slides": slides}


def _node_depth(node_id: str, parent_map: dict[str, str | None], cache: dict[str, int]) -> int:
    if node_id in cache:
        return cache[node_id]
    parent = parent_map.get(node_id)
    if parent is None:
        cache[node_id] = 0
        return 0
    depth = 1 + _node_depth(parent, parent_map, cache)
    cache[node_id] = depth
    return depth


def parse_mindmap(
    raw: str | dict[str, Any],
    sources: list[PackedSource],
) -> dict[str, Any] | None:
    data = raw if isinstance(raw, dict) else _parse_json_text(str(raw))
    if not data:
        return None

    rows = data.get("nodes")
    if not isinstance(rows, list) or not rows:
        return None

    nodes: list[dict[str, Any]] = []
    parent_map: dict[str, str | None] = {}
    depth_cache: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id") or "").strip()
        label = str(row.get("label") or "").strip()
        if not node_id or not label:
            continue
        parent_id = row.get("parent_id")
        parent_str = str(parent_id).strip() if parent_id not in (None, "", "null") else None
        parent_map[node_id] = parent_str

    root_label = str(data.get("root_label") or "").strip()
    if not any(v is None for v in parent_map.values()):
        root_id = "root"
        root_label = root_label or "Topic"
        nodes.append(
            {
                "id": root_id,
                "label": root_label[:80],
                "parent_id": None,
                "collapsed": False,
                "source_ref": _source_ref_from_index(1, sources) if sources else None,
            }
        )
        parent_map[root_id] = None

    for row in rows:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id") or "").strip()
        label = str(row.get("label") or "").strip()
        if not node_id or not label:
            continue
        parent_id = row.get("parent_id")
        parent_str = str(parent_id).strip() if parent_id not in (None, "", "null") else None
        depth = _node_depth(node_id, parent_map, depth_cache)
        if depth >= MAX_MINDMAP_DEPTH:
            continue
        try:
            src_idx = int(row.get("source_index") or 1)
        except (TypeError, ValueError):
            src_idx = 1
        nodes.append(
            {
                "id": node_id[:64],
                "label": label[:80],
                "parent_id": parent_str[:64] if parent_str else None,
                "collapsed": False,
                "source_ref": _source_ref_from_index(src_idx, sources),
            }
        )

    if len(nodes) < 2:
        return None
    return {"nodes": nodes}
