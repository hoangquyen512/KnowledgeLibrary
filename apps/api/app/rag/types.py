from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class RetrievalHit:
    chunk_id: UUID
    document_id: UUID
    space_id: UUID
    title: str
    snippet: str
    score: float
    chunk_index: int
    section_heading: str = ""
    source_url: str | None = None
    space_key: str | None = None
    parent_section: str = ""
    content: str = ""
    heading_path: str = ""
    source_id: UUID | None = None
    citation_label: str | None = None
