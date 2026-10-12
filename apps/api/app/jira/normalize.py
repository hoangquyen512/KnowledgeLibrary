"""Normalize Jira issues into RAG-friendly documents."""

from __future__ import annotations

from typing import Any

from app.ingestion.parsers import ChunkHint, NormalizedDocument, NormalizedSection
from app.models.document import DocumentType
from app.models.source import SourceType


def _adf_or_text(value: Any) -> str:
    """Extract plain text from Jira ADF / HTML / string fields."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if value.get("type") == "doc" or "content" in value:
            return _walk_adf(value).strip()
        if "text" in value:
            return str(value.get("text") or "").strip()
    return str(value).strip()


def _walk_adf(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(_walk_adf(n) for n in node)
    if not isinstance(node, dict):
        return ""
    ntype = node.get("type")
    text = node.get("text") or ""
    children = node.get("content") or []
    child_text = "\n".join(_walk_adf(c) for c in children)
    if ntype in {"paragraph", "heading", "blockquote", "listItem"}:
        return (text + "\n" + child_text).strip()
    if ntype in {"bulletList", "orderedList"}:
        return child_text
    if ntype == "hardBreak":
        return "\n"
    return (text + child_text).strip() if text or child_text else ""


def _field(fields: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in fields and fields[key] is not None:
            return fields[key]
    return None


def _name_of(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return str(obj.get("displayName") or obj.get("name") or obj.get("value") or "")
    return str(obj)


def normalize_jira_issue(
    issue: dict[str, Any],
    *,
    base_url: str,
    include: dict[str, bool] | None = None,
) -> NormalizedDocument:
    include = include or {}
    fields = issue.get("fields") or {}
    key = str(issue.get("key") or "")
    summary = str(_field(fields, "summary") or "").strip() or key
    issue_type = _name_of(_field(fields, "issuetype"))
    status = _name_of(_field(fields, "status"))
    priority = _name_of(_field(fields, "priority"))
    assignee = _name_of(_field(fields, "assignee"))
    reporter = _name_of(_field(fields, "reporter"))
    labels = _field(fields, "labels") or []
    if not isinstance(labels, list):
        labels = [str(labels)]
    components = _field(fields, "components") or []
    component_names = [_name_of(c) for c in components if isinstance(c, dict | str)]
    created = str(_field(fields, "created") or "")
    updated = str(_field(fields, "updated") or "")
    description = (
        _adf_or_text(_field(fields, "description")) if include.get("description", True) else ""
    )

    ac = ""
    if include.get("acceptance_criteria", True):
        for fname, fval in fields.items():
            lname = str(fname).lower()
            if "acceptance" in lname:
                ac = _adf_or_text(fval)
                if ac:
                    break

    comments_text = ""
    if include.get("comments", True):
        comment_block = _field(fields, "comment") or {}
        comments = comment_block.get("comments") if isinstance(comment_block, dict) else []
        parts: list[str] = []
        for c in comments or []:
            author = _name_of(c.get("author"))
            body = _adf_or_text(c.get("body"))
            if body:
                parts.append(f"- {author}: {body}")
        comments_text = "\n".join(parts)

    history_text = ""
    if include.get("change_history", False):
        changelog = issue.get("changelog") or {}
        histories = changelog.get("histories") or []
        hparts: list[str] = []
        for h in histories:
            author = _name_of(h.get("author"))
            created_h = h.get("created") or ""
            for item in h.get("items") or []:
                field = item.get("field") or ""
                frm = item.get("fromString") or ""
                to = item.get("toString") or ""
                hparts.append(f"- [{created_h}] {author}: {field} {frm} → {to}")
        history_text = "\n".join(hparts)

    attachment_meta = ""
    if include.get("attachments", True):
        atts = _field(fields, "attachment") or []
        anames = []
        for a in atts:
            if isinstance(a, dict):
                anames.append(str(a.get("filename") or a.get("id") or ""))
        if anames:
            attachment_meta = "Attachments: " + ", ".join(n for n in anames if n)

    parent = _field(fields, "parent")
    parent_key = ""
    if isinstance(parent, dict):
        parent_key = str(parent.get("key") or "")
    epic_key = ""
    epic_link = _field(fields, "customfield_10014", "epic")
    if isinstance(epic_link, str):
        epic_key = epic_link
    elif isinstance(epic_link, dict):
        epic_key = str(epic_link.get("key") or "")

    source_url = f"{base_url.rstrip('/')}/browse/{key}" if key else None

    lines = [
        f"Issue Key: {key}",
        f"Title: {summary}",
        "",
        f"Status: {status}",
        f"Priority: {priority}",
        f"Type: {issue_type}",
        f"Assignee: {assignee}",
        f"Reporter: {reporter}",
        f"Labels: {', '.join(str(label) for label in labels)}",
        f"Components: {', '.join(component_names)}",
        f"Created: {created}",
        f"Updated: {updated}",
    ]
    sections: list[NormalizedSection] = []
    chunks: list[ChunkHint] = []

    header = "\n".join(lines)
    sections.append(NormalizedSection(title="Overview", text=header))
    chunks.append(
        ChunkHint(
            text=header,
            position=0,
            metadata={
                "issue_key": key,
                "section": "overview",
                "citation_label": f"{key} — {summary}",
            },
        )
    )

    if description and include.get("description", True):
        sections.append(NormalizedSection(title="Description", text=description))
        chunks.append(
            ChunkHint(
                text=f"Issue Key: {key}\nTitle: {summary}\n\nDescription:\n{description}",
                position=len(chunks),
                metadata={
                    "issue_key": key,
                    "section": "description",
                    "citation_label": f"{key} — {summary}",
                },
            )
        )
        lines.extend(["", "Description:", description])

    if ac:
        sections.append(NormalizedSection(title="Acceptance Criteria", text=ac))
        chunks.append(
            ChunkHint(
                text=f"Issue Key: {key}\nAcceptance Criteria:\n{ac}",
                position=len(chunks),
                metadata={
                    "issue_key": key,
                    "section": "acceptance_criteria",
                    "citation_label": f"{key} — {summary}",
                },
            )
        )
        lines.extend(["", "Acceptance Criteria:", ac])

    if comments_text:
        sections.append(NormalizedSection(title="Comments", text=comments_text))
        chunks.append(
            ChunkHint(
                text=f"Issue Key: {key}\nComments:\n{comments_text}",
                position=len(chunks),
                metadata={
                    "issue_key": key,
                    "section": "comments",
                    "citation_label": f"{key} — {summary}",
                },
            )
        )
        lines.extend(["", "Comments:", comments_text])

    if history_text:
        sections.append(NormalizedSection(title="Change History", text=history_text))
        chunks.append(
            ChunkHint(
                text=f"Issue Key: {key}\nChange History:\n{history_text}",
                position=len(chunks),
                metadata={
                    "issue_key": key,
                    "section": "change_history",
                    "citation_label": f"{key} — {summary}",
                },
            )
        )
        lines.extend(["", "Change History:", history_text])

    if attachment_meta:
        lines.extend(["", attachment_meta])

    parent_ext = None
    if isinstance(parent, dict) and parent.get("id"):
        parent_ext = str(parent.get("id"))

    return NormalizedDocument(
        title=f"{key} — {summary}" if key else summary,
        document_type=DocumentType.JIRA_ISSUE,
        source_type=SourceType.JIRA,
        source_locator=key,
        normalized_text="\n".join(lines),
        external_id=str(issue.get("id") or key),
        sections=sections,
        chunk_hints=chunks,
        raw_metadata={
            "issue_key": key,
            "issue_type": issue_type,
            "status": status,
            "priority": priority,
            "assignee": assignee,
            "reporter": reporter,
            "labels": labels,
            "components": component_names,
            "created_at": created,
            "updated_at": updated,
            "parent_key": parent_key or None,
            "epic_key": epic_key or None,
            "summary": summary,
        },
        external_url=source_url,
        parent_external_id=parent_ext,
        external_version=updated or None,
    )
