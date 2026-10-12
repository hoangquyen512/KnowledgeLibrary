"""Export Space Source pages as Markdown ZIP for NotebookLM import."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from typing import Any
from uuid import UUID

from bs4 import BeautifulSoup, NavigableString, Tag

from app.ingestion.normalize import table_to_markdown

MAX_EXPORT_PAGES = 2000

_SAFE_SLUG = re.compile(r"[^\w.\-]+", re.UNICODE)
_MULTI_NL = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class ExportPage:
    id: UUID
    title: str
    external_url: str | None
    parent_id: UUID | None
    depth: int
    position: int
    raw_content: str | None
    normalized_content: str | None


def safe_slug(text: str, *, fallback: str = "page", max_len: int = 80) -> str:
    raw = (text or "").strip() or fallback
    slug = _SAFE_SLUG.sub("_", raw).strip("._-") or fallback
    return slug[:max_len]


def html_to_markdown(html: str) -> str:
    """Convert stored page HTML to Markdown. Images become alt-text notes only."""
    cleaned = (html or "").strip()
    if not cleaned:
        return ""

    soup = BeautifulSoup(cleaned, "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "embed"]):
        tag.decompose()

    for img in list(soup.find_all("img")):
        alt = (img.get("alt") or img.get("title") or "").strip()
        note = f"\n*[Image: {alt}]*\n" if alt else "\n*[Image omitted]*\n"
        img.replace_with(NavigableString(note))

    for table in list(soup.find_all("table")):
        md = table_to_markdown(table)
        table.replace_with(NavigableString(f"\n{md}\n" if md else ""))

    root = soup.body if soup.body else soup
    parts: list[str] = []
    for child in root.children:
        chunk = _node_to_markdown(child).strip()
        if chunk:
            parts.append(chunk)

    text = "\n\n".join(parts)
    text = unescape(text)
    text = _MULTI_NL.sub("\n\n", text).strip()
    return text


def _inline_markdown(node: Tag | NavigableString | Any) -> str:
    if isinstance(node, NavigableString):
        return str(node).replace("\n", " ")
    if not isinstance(node, Tag):
        return ""
    name = (node.name or "").lower()
    if name in {"br"}:
        return "\n"
    if name in {"strong", "b"}:
        inner = "".join(_inline_markdown(c) for c in node.children).strip()
        return f"**{inner}**" if inner else ""
    if name in {"em", "i"}:
        inner = "".join(_inline_markdown(c) for c in node.children).strip()
        return f"*{inner}*" if inner else ""
    if name == "code":
        inner = node.get_text("", strip=False)
        return f"`{inner}`"
    if name == "a":
        label = "".join(_inline_markdown(c) for c in node.children).strip() or node.get_text(
            " ", strip=True
        )
        href = (node.get("href") or "").strip()
        if href and label:
            return f"[{label}]({href})"
        return label
    return "".join(_inline_markdown(c) for c in node.children)


def _node_to_markdown(node: Tag | NavigableString | Any) -> str:
    if isinstance(node, NavigableString):
        text = str(node).strip()
        return text
    if not isinstance(node, Tag):
        return ""

    name = (node.name or "").lower()
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        title = node.get_text(" ", strip=True)
        return f"{'#' * level} {title}" if title else ""
    if name == "p":
        return _inline_markdown(node).strip()
    if name in {"ul", "ol"}:
        lines: list[str] = []
        items = [c for c in node.children if isinstance(c, Tag) and (c.name or "").lower() == "li"]
        for idx, li in enumerate(items, start=1):
            body = _inline_markdown(li).strip()
            if not body:
                continue
            prefix = f"{idx}." if name == "ol" else "-"
            lines.append(f"{prefix} {body}")
        return "\n".join(lines)
    if name == "li":
        return _inline_markdown(node).strip()
    if name == "pre":
        code = node.get_text("", strip=False).strip("\n")
        return f"```\n{code}\n```"
    if name == "blockquote":
        inner = _node_to_markdown_children(node).strip()
        return "\n".join(f"> {line}" if line else ">" for line in inner.splitlines())
    if name == "hr":
        return "---"
    if name in {"div", "section", "article", "span", "body"}:
        return _node_to_markdown_children(node)
    return _inline_markdown(node).strip()


def _node_to_markdown_children(node: Tag) -> str:
    parts: list[str] = []
    for child in node.children:
        chunk = _node_to_markdown(child).strip()
        if chunk:
            parts.append(chunk)
    return "\n\n".join(parts)


def document_path(
    pages_by_id: dict[UUID, ExportPage],
    page: ExportPage,
) -> str:
    parts: list[str] = []
    current: ExportPage | None = page
    seen: set[UUID] = set()
    while current is not None:
        if current.id in seen:
            break
        seen.add(current.id)
        parts.append(current.title or "Untitled")
        if current.parent_id is None:
            break
        current = pages_by_id.get(current.parent_id)
    return " / ".join(reversed(parts))


def page_markdown(
    page: ExportPage,
    *,
    source_name: str,
    path: str,
    heading_level: int = 1,
    include_frontmatter: bool = True,
) -> str:
    body = ""
    raw = (page.raw_content or "").strip()
    if raw:
        body = html_to_markdown(raw)
    if not body:
        body = (page.normalized_content or "").strip()

    title = (page.title or "Untitled").strip()
    level = max(1, min(6, heading_level))
    parts: list[str] = []
    if include_frontmatter:
        frontmatter_lines = [
            "---",
            f"title: {_yaml_scalar(title)}",
            f"source: {_yaml_scalar(source_name)}",
            f"path: {_yaml_scalar(path)}",
        ]
        if page.external_url:
            frontmatter_lines.append(f"external_url: {_yaml_scalar(page.external_url)}")
        frontmatter_lines.append("---")
        parts.append("\n".join(frontmatter_lines))
    parts.append(f"{'#' * level} {title}")
    if body:
        parts.append(body)
    return "\n\n".join(parts).rstrip() + "\n"


def _yaml_scalar(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return '""'
    needs_quote = (
        any(ch in text for ch in ":#{}[]&*!|>'\"%@`")
        or any(ch.isspace() for ch in text)
        or text[:1] in "-?"
    )
    if needs_quote:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def unique_zip_name(index: int, title: str, used: set[str]) -> str:
    base = f"{index:04d}-{safe_slug(title)}.md"
    if base not in used:
        used.add(base)
        return base
    n = 2
    while True:
        candidate = f"{index:04d}-{safe_slug(title)}-{n}.md"
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def bundle_root_id(
    page: ExportPage,
    pages_by_id: dict[UUID, ExportPage],
    *,
    group_depth: int = 2,
) -> UUID:
    """Group under the ancestor at ``group_depth`` (default tree level 2).

    Pages shallower than ``group_depth`` are their own bundle roots.
    Deeper pages roll up into the nearest ancestor at exactly ``group_depth``.
    """
    chain: list[ExportPage] = []
    current: ExportPage | None = page
    seen: set[UUID] = set()
    while current is not None:
        if current.id in seen:
            break
        seen.add(current.id)
        chain.append(current)
        if current.parent_id is None:
            break
        current = pages_by_id.get(current.parent_id)
    chain.reverse()  # root → leaf

    for node in chain:
        if node.depth == group_depth:
            return node.id
    # No level-N ancestor: keep the page (shallow leaf / mid node) as its own file.
    return page.id


def bundle_markdown(
    pages: list[ExportPage],
    *,
    source_name: str,
    pages_by_id: dict[UUID, ExportPage],
    bundle_title: str,
    bundle_path: str,
) -> str:
    """Merge pages in tree order into one Markdown document."""
    ordered = sorted(
        pages,
        key=lambda p: (p.depth, p.position, (p.title or "").lower(), str(p.id)),
    )
    root = ordered[0] if ordered else None
    sections: list[str] = [
        "\n".join(
            [
                "---",
                f"title: {_yaml_scalar(bundle_title)}",
                f"source: {_yaml_scalar(source_name)}",
                f"path: {_yaml_scalar(bundle_path)}",
                f"pages: {len(ordered)}",
                "---",
            ]
        )
    ]
    for page in ordered:
        path = document_path(pages_by_id, page)
        # Root of the bundle keeps H1; nested pages use depth relative to bundle root.
        if root and page.id == root.id:
            heading = 1
        else:
            heading = min(6, max(2, page.depth - (root.depth if root else 0) + 1))
        sections.append(
            page_markdown(
                page,
                source_name=source_name,
                path=path,
                heading_level=heading,
                include_frontmatter=False,
            ).rstrip()
        )
    return "\n\n".join(sections).rstrip() + "\n"


def count_export_files(
    pages: list[ExportPage],
    *,
    group_depth: int,
) -> int:
    """How many ``.md`` files ``build_md_zip`` would produce for ``group_depth``."""
    if not pages:
        return 0
    if group_depth <= 0:
        return len(pages)
    depth = max(1, min(20, int(group_depth)))
    by_id = {p.id: p for p in pages}
    roots: set[UUID] = set()
    for page in pages:
        roots.add(bundle_root_id(page, by_id, group_depth=depth))
    return len(roots)


def preview_export_file_counts(
    pages: list[ExportPage],
    *,
    depths: list[int] | None = None,
) -> dict[str, int]:
    """Map group_depth → file count for UI subtexts."""
    levels = depths if depths is not None else [0, 1, 2, 3, 4, 5]
    return {str(d): count_export_files(pages, group_depth=d) for d in levels}


def build_md_zip(
    pages: list[ExportPage],
    *,
    source_name: str,
    group_depth: int = 2,
) -> bytes:
    """Zip Markdown bundles grouped by tree level ``group_depth``.

    ``group_depth <= 0`` → one ``.md`` file per page (lightest for NotebookLM).
    ``group_depth >= 1`` → deeper pages merge into the ancestor at that depth
    (lower depth = fewer, larger files).
    """
    ordered = sorted(pages, key=lambda p: (p.depth, p.position, (p.title or "").lower(), str(p.id)))
    by_id = {p.id: p for p in ordered}

    bundles: dict[UUID, list[ExportPage]] = {}
    if group_depth <= 0:
        for page in ordered:
            bundles[page.id] = [page]
    else:
        depth = max(1, min(20, int(group_depth)))
        for page in ordered:
            root_id = bundle_root_id(page, by_id, group_depth=depth)
            bundles.setdefault(root_id, []).append(page)

    # Stable order: by bundle root tree position.
    root_order = sorted(
        bundles.keys(),
        key=lambda rid: (
            by_id[rid].depth,
            by_id[rid].position,
            (by_id[rid].title or "").lower(),
            str(rid),
        ),
    )

    used_names: set[str] = set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, root_id in enumerate(root_order, start=1):
            group = bundles[root_id]
            root = by_id[root_id]
            bundle_path = document_path(by_id, root)
            if len(group) == 1 and group[0].id == root_id:
                content = page_markdown(
                    group[0],
                    source_name=source_name,
                    path=bundle_path,
                )
            else:
                content = bundle_markdown(
                    group,
                    source_name=source_name,
                    pages_by_id=by_id,
                    bundle_title=root.title or "Untitled",
                    bundle_path=bundle_path,
                )
            name = unique_zip_name(idx, root.title, used_names)
            zf.writestr(name, content.encode("utf-8"))
    return buffer.getvalue()
