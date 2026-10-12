from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html import unescape

from bs4 import BeautifulSoup, NavigableString, Tag

SCRIPT_OR_EVENT = re.compile(r"^on\w+", re.I)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return unescape(re.sub(r"\n{3,}", "\n\n", text))


def sanitize_html(html: str) -> str:
    """Strip scripts/handlers; keep structure + img/src for rewrite."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "embed"]):
        tag.decompose()
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        for name in list(attrs):
            if SCRIPT_OR_EVENT.match(name) or name.lower() in {"srcdoc"}:
                del tag.attrs[name]
    return str(soup)


def rewrite_attachment_urls(
    html: str,
    *,
    filename_to_attachment_id: dict[str, str],
    api_prefix: str = "/api/v1",
) -> str:
    """Rewrite Confluence download URLs / img src to internal attachment content URLs."""
    soup = BeautifulSoup(html or "", "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        # Confluence often uses /download/attachments/{pageId}/{filename}
        fname = src.rsplit("/", 1)[-1].split("?")[0]
        fname = unescape(fname)
        att_id = filename_to_attachment_id.get(fname) or filename_to_attachment_id.get(
            fname.lower()
        )
        if att_id:
            img["src"] = f"{api_prefix}/attachments/{att_id}/content"
            img["data-kl-attachment-id"] = att_id
    return str(soup)


def replace_confluence_images(
    html: str,
    *,
    filename_to_attachment_id: dict[str, str],
    api_prefix: str = "/api/v1",
) -> str:
    """Convert Confluence ``ac:image`` + ``ri:attachment`` macros into real ``<img>`` tags.

    Browsers ignore ``ac:*`` / ``ri:*`` tags, so pages only show captions like "Hình 1"
    unless we rewrite macros to attachment content URLs.
    """
    if not html:
        return html
    lower = html.lower()
    if "ac:image" not in lower and "ri:attachment" not in lower:
        return html

    soup = BeautifulSoup(html, "html.parser")
    images = soup.find_all(
        lambda tag: tag.name and tag.name.lower() in {"ac:image", "image"}
    )
    for node in images:
        filename = ""
        external_done = False
        for child in node.find_all(["ri:attachment", "attachment", "ri:url", "url"]):
            cname = (child.name or "").lower()
            if cname in {"ri:attachment", "attachment"}:
                filename = (
                    child.get("ri:filename")
                    or child.get("filename")
                    or ""
                ).strip()
                if filename:
                    break
            if cname in {"ri:url", "url"}:
                href = (
                    child.get("ri:value") or child.get("value") or child.get("href") or ""
                ).strip()
                if href.startswith("http://") or href.startswith("https://"):
                    img = soup.new_tag("img")
                    img["src"] = href
                    img["alt"] = href.rsplit("/", 1)[-1]
                    img["class"] = "kl-confluence-image"
                    img["loading"] = "lazy"
                    _copy_ac_image_size(node, img)
                    node.replace_with(img)
                    external_done = True
                    break
        if external_done:
            continue
        if not filename:
            node.decompose()
            continue

        att_id = _lookup_attachment_id(filename_to_attachment_id, filename, unescape(filename))
        if not att_id:
            note = soup.new_tag("p")
            note["class"] = "kl-image-missing"
            note.string = f"[Image missing: {filename}]"
            node.replace_with(note)
            continue

        img = soup.new_tag("img")
        img["src"] = f"{api_prefix}/attachments/{att_id}/content"
        img["alt"] = filename
        img["class"] = "kl-confluence-image"
        img["loading"] = "lazy"
        img["data-kl-attachment-id"] = att_id
        _copy_ac_image_size(node, img)
        node.replace_with(img)

    return str(soup)


def _copy_ac_image_size(ac_node, img_tag) -> None:
    width = ac_node.get("ac:width") or ac_node.get("width")
    height = ac_node.get("ac:height") or ac_node.get("height")
    style_parts: list[str] = []
    if width:
        img_tag["width"] = str(width)
        style_parts.append(f"max-width:{width}px")
    if height:
        img_tag["height"] = str(height)
    if style_parts:
        img_tag["style"] = ";".join(style_parts) + ";height:auto"


def _lookup_attachment_id(
    filename_to_attachment_id: dict[str, str], *candidates: str
) -> str | None:
    for name in candidates:
        if not name:
            continue
        att_id = filename_to_attachment_id.get(name) or filename_to_attachment_id.get(name.lower())
        if att_id:
            return att_id
    return None


def replace_drawio_macros_with_images(
    html: str,
    *,
    filename_to_attachment_id: dict[str, str],
    api_prefix: str = "/api/v1",
) -> str:
    """Replace Confluence draw.io macros with static PNG previews.

    Browsers ignore ``ac:*`` tags and dump parameter text into the page
    (e.g. ``trueOnboard SSC IDBzmA7…``). Prefer the companion ``{diagramName}.png``
    that Confluence exports next to the .drawio attachment.
    """
    if not html or "drawio" not in html.lower():
        return html

    soup = BeautifulSoup(html, "html.parser")
    macros = soup.find_all(
        lambda tag: tag.name
        and tag.name.lower() in {"ac:structured-macro", "structured-macro"}
        and (tag.get("ac:name") or tag.get("name") or "").lower() == "drawio"
    )
    for macro in macros:
        diagram_name = ""
        for param in macro.find_all(["ac:parameter", "parameter"]):
            pname = (param.get("ac:name") or param.get("name") or "").strip()
            if pname == "diagramName":
                diagram_name = param.get_text(strip=True)
                break
        if not diagram_name:
            macro.decompose()
            continue

        png_id = _lookup_attachment_id(
            filename_to_attachment_id,
            f"{diagram_name}.png",
            f"{diagram_name}.PNG",
            f"{diagram_name}.jpg",
            f"{diagram_name}.jpeg",
            f"{diagram_name}.svg",
        )
        if png_id:
            img = soup.new_tag("img")
            img["src"] = f"{api_prefix}/attachments/{png_id}/content"
            img["alt"] = diagram_name
            img["class"] = "kl-drawio-preview"
            img["loading"] = "lazy"
            img["data-kl-diagram"] = diagram_name
            macro.replace_with(img)
            continue

        # No preview image — never leave parameter text; show a short placeholder.
        note = soup.new_tag("div")
        note["class"] = "kl-drawio-missing"
        note["data-kl-diagram"] = diagram_name
        note.string = f"[Diagram preview unavailable: {diagram_name}]"
        macro.replace_with(note)

    return str(soup)


def content_checksum(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def is_drawio_filename(filename: str, media_type: str | None = None) -> bool:
    name = (filename or "").lower()
    mt = (media_type or "").lower()
    if name.endswith((".drawio", ".drawio.xml", ".dio")):
        return True
    if "drawio" in mt or "diagram+xml" in mt or "jgraph.mxfile" in mt or "mxfile" in mt:
        return True
    if name.endswith(".xml") and "draw" in name:
        return True
    return False


HEADING_TAGS = frozenset({"h1", "h2", "h3"})


@dataclass
class HeadingChunkPiece:
    content: str
    section_heading: str
    heading_path: str
    parent_section: str


def build_embed_prefix(
    *,
    page_title: str,
    section_heading: str,
    space_key: str | None,
) -> str:
    page = (page_title or "Untitled").strip()
    section = (section_heading or page).strip()
    space = (space_key or "unknown").strip()
    return f"Page: {page} | Section: {section} | Space: {space}"


def build_embed_text(
    *,
    page_title: str,
    section_heading: str,
    space_key: str | None,
    content: str,
) -> str:
    prefix = build_embed_prefix(
        page_title=page_title,
        section_heading=section_heading,
        space_key=space_key,
    )
    return f"{prefix}\n\n{(content or '').strip()}"


def table_to_markdown(table: Tag) -> str:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        rows.append([cell.get_text(" ", strip=True) for cell in cells])
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    divider = ["---"] * width
    body = normalized[1:] if len(normalized) > 1 else []
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(divider) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _replace_tables_with_markdown(soup: BeautifulSoup) -> None:
    for table in list(soup.find_all("table")):
        md = table_to_markdown(table)
        if md:
            table.replace_with(NavigableString(f"\n{md}\n"))
        else:
            table.decompose()


def _element_plain_text(element: Tag | NavigableString) -> str:
    if isinstance(element, NavigableString):
        return str(element).strip()
    if not isinstance(element, Tag):
        return ""
    name = (element.name or "").lower()
    if name == "table":
        return table_to_markdown(element)
    if name in HEADING_TAGS:
        return element.get_text(" ", strip=True)
    return element.get_text("\n", strip=True)


def _walk_section_blocks(root: Tag) -> list[tuple[str, str, int]]:
    """Return ordered blocks: ('heading'|'text', content, heading_level)."""
    blocks: list[tuple[str, str, int]] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    blocks.append(("text", text, 0))
                continue
            if not isinstance(child, Tag):
                continue
            name = (child.name or "").lower()
            if name in HEADING_TAGS:
                blocks.append(("heading", child.get_text(" ", strip=True), int(name[1])))
            elif name == "table":
                md = table_to_markdown(child)
                if md:
                    blocks.append(("text", md, 0))
            elif child.find(list(HEADING_TAGS) + ["table"]):
                walk(child)
            else:
                text = _element_plain_text(child)
                if text:
                    blocks.append(("text", text, 0))

    walk(root)
    return blocks


def chunk_html_by_headings(
    html: str,
    *,
    page_title: str = "",
    max_chars: int = 1500,
    overlap: int = 80,
) -> list[HeadingChunkPiece]:
    """Split sanitized HTML into heading-aware chunks (tables stay intact)."""
    cleaned = (html or "").strip()
    if not cleaned:
        return []

    soup = BeautifulSoup(cleaned, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    _replace_tables_with_markdown(soup)
    root = soup.body if soup.body else soup

    blocks = _walk_section_blocks(root)
    if not blocks:
        fallback = html_to_text(cleaned)
        if not fallback.strip():
            return []
        title = (page_title or "Document").strip()
        return [
            HeadingChunkPiece(
                content=piece,
                section_heading=title,
                heading_path=title,
                parent_section=fallback,
            )
            for piece in chunk_text(fallback, max_chars=max_chars, overlap=overlap)
        ]

    sections: list[tuple[str, str, str]] = []
    heading_stack: list[tuple[int, str]] = []
    current_heading = (page_title or "Document").strip()
    current_parts: list[str] = []

    def heading_path() -> str:
        parts = [page_title] if page_title else []
        parts.extend(text for level, text in heading_stack if text)
        seen: list[str] = []
        for part in parts:
            if part and (not seen or seen[-1] != part):
                seen.append(part)
        return " > ".join(seen) if seen else current_heading

    def flush() -> None:
        nonlocal current_parts
        body = "\n\n".join(part for part in current_parts if part.strip()).strip()
        if body:
            sections.append((current_heading, heading_path(), body))
        current_parts = []

    for kind, content, level in blocks:
        if kind == "heading" and content:
            flush()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, content))
            current_heading = content
            continue
        if content.strip():
            current_parts.append(content.strip())
    flush()

    if not sections:
        fallback = html_to_text(cleaned)
        title = (page_title or "Document").strip()
        return [
            HeadingChunkPiece(
                content=piece,
                section_heading=title,
                heading_path=title,
                parent_section=fallback,
            )
            for piece in chunk_text(fallback, max_chars=max_chars, overlap=overlap)
        ]

    pieces: list[HeadingChunkPiece] = []
    for section_heading, path, section_body in sections:
        sub_chunks = chunk_text(section_body, max_chars=max_chars, overlap=overlap)
        if not sub_chunks:
            continue
        parent = section_body[:4000]
        for sub in sub_chunks:
            pieces.append(
                HeadingChunkPiece(
                    content=sub,
                    section_heading=section_heading,
                    heading_path=path,
                    parent_section=parent,
                )
            )
    return pieces


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        if end < len(cleaned):
            # prefer break on paragraph/sentence
            window = cleaned[start:end]
            br = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if br > max_chars // 3:
                end = start + br + 1
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks
