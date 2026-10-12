from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# Approximate char budget for LLM context (~80k chars)
DEFAULT_CHAR_BUDGET = 80_000
MAX_DOCUMENTS = 30
MAX_BULLETS_PER_SLIDE = 6
MAX_MINDMAP_DEPTH = 4


@dataclass
class PackedSource:
    index: int
    document_id: UUID
    chunk_id: UUID | None
    space_id: UUID
    title: str
    content: str
    section_heading: str
    source_url: str | None
    snippet: str


@dataclass
class PackResult:
    sources: list[PackedSource]
    total_chars: int
    map_reduce_used: bool
    documents_capped: bool
    document_count: int


def estimate_chars(sources: list[PackedSource]) -> int:
    return sum(len(s.content) + len(s.title) + 40 for s in sources)


def build_context_blocks(sources: list[PackedSource]) -> str:
    lines: list[str] = []
    for src in sources:
        heading = src.section_heading or src.title
        lines.append(f"[{src.index}] {src.title} — {heading}")
        lines.append(src.content[:8000])
        lines.append("")
    return "\n".join(lines)


def snippet_from_content(content: str, max_len: int = 240) -> str:
    cleaned = " ".join((content or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    idx = cut.rfind(" ")
    if idx > max_len // 3:
        return cut[:idx] + "…"
    return cut + "…"
