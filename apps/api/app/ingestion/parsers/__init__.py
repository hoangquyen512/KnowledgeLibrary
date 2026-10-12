"""Document parser registry and normalized document types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class NormalizedSection:
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkHint:
    text: str
    position: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedDocument:
    title: str
    document_type: str
    source_type: str
    source_locator: str
    normalized_text: str
    external_id: str
    sections: list[NormalizedSection] = field(default_factory=list)
    chunk_hints: list[ChunkHint] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    external_url: str | None = None
    parent_external_id: str | None = None
    external_version: str | None = None


@dataclass
class ParseResult:
    documents: list[NormalizedDocument]
    preview: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class DocumentParser(Protocol):
    source_type: str

    def parse(self, data: bytes, *, filename: str, options: dict[str, Any] | None = None) -> ParseResult:
        ...


_REGISTRY: dict[str, DocumentParser] = {}


def register_parser(parser: DocumentParser) -> DocumentParser:
    _REGISTRY[parser.source_type] = parser
    return parser


def get_parser(source_type: str) -> DocumentParser:
    parser = _REGISTRY.get(source_type)
    if parser is None:
        raise KeyError(f"No parser registered for source type: {source_type}")
    return parser


def list_parsers() -> list[str]:
    return sorted(_REGISTRY.keys())


def ensure_parsers_loaded() -> None:
    """Import concrete parsers so registry is populated."""
    from app.ingestion.parsers import csv as _csv  # noqa: F401
    from app.ingestion.parsers import docx as _docx  # noqa: F401
    from app.ingestion.parsers import excel as _excel  # noqa: F401
    from app.ingestion.parsers import pdf as _pdf  # noqa: F401
    from app.ingestion.parsers import pptx as _pptx  # noqa: F401
