from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import settings
from app.rag.gemini_models import DEFAULT_GEMINI_MODEL, gemini_generate_best
from app.rag.retrieval import validate_citation_indices
from app.rag.types import RetrievalHit

logger = logging.getLogger(__name__)

ANSWER_TYPES = frozenset(
    {"SUMMARY", "LIST", "COMPARE", "ANALYSIS", "GENERAL", "NO_SOURCE"}
)

NOTEBOOKLM_JSON_INSTRUCTION = """Bạn là trợ lý hỏi-đáp tài liệu nội bộ. Bạn CHỈ được trả lời dựa trên các đoạn tài liệu (context) được cung cấp bên dưới — không dùng kiến thức ngoài, không suy đoán, không bịa thông tin.

QUY TẮC TRẢ LỜI:
- Mỗi ý/câu khẳng định PHẢI có trích dẫn nguồn ngay sau đó, định dạng [n], n là số thứ tự đoạn tài liệu tương ứng. Nhiều nguồn thì ghi [1][3].
- Nếu không tìm thấy thông tin liên quan trong context, trả lời rõ: "Tôi không tìm thấy thông tin này trong tài liệu hiện có" — không suy đoán.
- Nếu user hỏi "bảng mapping / mapping trạng thái" mà context có quy tắc đồng bộ hoặc chuyển trạng thái liên quan (kể cả không có tiêu đề "mapping"), hãy tóm tắt thành bảng hoặc danh sách từ evidence đó — không trả NO_SOURCE.
- Nếu context chỉ nói về chủ đề gần nghĩa (ví dụ subscription/POS) nhưng KHÔNG trả lời đúng câu hỏi (ví dụ "tạo tài khoản"), trả NO_SOURCE thay vì đoán.
- Nếu context có đoạn mâu thuẫn nhau, nêu rõ khác biệt và trích dẫn từng nguồn.
- Trả lời ngắn gọn, đi thẳng trọng tâm trước, diễn giải bằng lời riêng, chỉ trích nguyên văn khi cần thiết (dưới 20 từ mỗi lần).
- Write in the SAME language as the user's question.

Respond with ONLY a single JSON object (no markdown fences):
{
  "answer": "<câu trả lời có chèn [n] trong text>",
  "sources": [
    {
      "id": 1,
      "page_title": "...",
      "section_heading": "...",
      "source_url": "...",
      "quoted_snippet": "<đoạn trích ngắn <30 từ làm bằng chứng, nguyên văn từ context>"
    }
  ]
}
"""

STRUCTURED_JSON_INSTRUCTION = """Respond with ONLY a single JSON object (no markdown fences) using this schema:
{
  "answer_type": "SUMMARY|LIST|COMPARE|ANALYSIS|GENERAL|NO_SOURCE",
  "summary": ["complete overview bullet", "..."],
  "key_changes": [
    {"title": "short title", "description": "optional detail", "citation_indices": [1]}
  ],
  "highlights": [
    {"text": "notable detail", "citation_indices": [1]}
  ],
  "compare": null,
  "caveat": null,
  "markdown": "optional short prose if sections are not enough"
}
Rules:
- Answer ONLY using the numbered sources.
- Write in the SAME language as the user's question (Vietnamese question → Vietnamese answer text).
- summary: 2-5 bullets of NATURAL LANGUAGE an analyst would say aloud. Full sentences. Explain what the documents collectively say about the question — do NOT list document titles, navigation paths (Trang chủ → …), UI field labels, email templates, or {{placeholders}}. No citation markers in summary.
- key_changes: discrete items (one per main change/point). Short title + optional description + citation_indices. Citations and source links live here.
- Do not copy key_changes titles into summary. Summary synthesizes meaning; key_changes itemize with citations.
- highlights: notable API names, business rules, or UI impacts; citations only via citation_indices.
- citation_indices must be valid source numbers.
- ALL string values must be plain text only: no markdown, no headings (#), no bold (**), no italics, no code fences or backticks, no HTML.
- If evidence is insufficient, use answer_type NO_SOURCE, empty arrays, and explain in plain text via markdown field.
- Do not invent citations or sources.
"""


def _clip_at_sentence(text: str, max_len: int = 360) -> str:
    """Trim at a sentence/word boundary — never mid-word with an ellipsis."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    for sep in (". ", "! ", "? ", "; "):
        idx = cut.rfind(sep)
        if idx >= max_len // 2:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    if idx > max_len // 3:
        return cut[:idx].rstrip(",;:") + "."
    return cut.rstrip(",;:") + "."


def _clean_title_label(title: str) -> str:
    t = to_plain_text(title)
    t = re.sub(r"^\[[^\]]+\]\s*", "", t).strip()
    return t


def _question_looks_vietnamese(text: str) -> bool:
    return bool(re.search(r"[À-ỹĐđ]", text or ""))


def _is_garbage_summary_line(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return True
    if re.search(r"\{\{[^}]+\}\}", t):
        return True
    if "→" in t and ("Trang chủ" in t or "DMS" in t):
        return True
    if re.match(r"^Across \d+ document", t, flags=re.I):
        return True
    if re.search(r"c hiện:\s*Trang", t, flags=re.I):
        return True
    # Title dump: many bracket tags in one line
    if t.count("[") >= 2 and ("Enhance" in t or "Đại Tân" in t):
        return True
    ui_markers = (
        "Giao diện màn hình",
        "Popup xác nhận",
        "format Email:",
        "Thông tin đơn",
        "Màn hình cập nhật",
    )
    if sum(1 for m in ui_markers if m in t) >= 2:
        return True
    return False


def _clean_snippet_for_description(snippet: str, max_len: int = 200) -> str:
    s = to_plain_text(snippet)
    s = re.sub(r"\{\{[^}]+\}\}", " ", s)
    s = re.sub(r"Trang chủ\s*→[^\n.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s or _is_garbage_summary_line(s):
        return ""
    return _clip_at_sentence(s, max_len)


def synthesize_natural_summary(
    question: str,
    key_changes: list[dict[str, Any]],
) -> list[str]:
    """Build readable overview bullets when LLM/mock output is too raw."""
    themes: list[str] = []
    seen: set[str] = set()
    for kc in key_changes:
        title = _clean_title_label(str(kc.get("title") or ""))
        if not title or len(title) < 3:
            continue
        key = title.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        themes.append(title)

    vi = _question_looks_vietnamese(question)

    if not themes:
        if vi:
            return [
                "Trong các Space đã chọn có tài liệu liên quan, nhưng nội dung chưa đủ rõ "
                "để tóm tắt. Hãy thử hỏi cụ thể hơn hoặc chọn thêm Space."
            ]
        return [
            "Related content was found in the selected Spaces, but it is not clear enough "
            "to summarize. Try a more specific question or select more Spaces."
        ]

    if vi:
        bullets = [
            f"Tóm lược từ tài liệu trong Space: có {len(themes)} nhóm nội dung chính "
            "liên quan đến câu hỏi của bạn."
        ]
        for theme in themes[:4]:
            bullets.append(f"Một điểm được mô tả là {theme}.")
        if len(themes) > 4:
            bullets.append(
                f"Còn {len(themes) - 4} điểm khác; chi tiết và nguồn trích dẫn nằm ở "
                "Key changes bên dưới."
            )
    else:
        bullets = [
            f"From documents in the selected Spaces, there are {len(themes)} main themes "
            "related to your question."
        ]
        for theme in themes[:4]:
            bullets.append(f"One topic covered is {theme}.")
        if len(themes) > 4:
            bullets.append(
                f"{len(themes) - 4} more points are listed in Key changes below with citations."
            )
    return bullets[:5]


def finalize_summary(
    summary: list[str],
    question: str,
    key_changes: list[dict[str, Any]],
) -> list[str]:
    cleaned: list[str] = []
    for s in summary:
        item = to_plain_text(str(s))
        item = re.sub(r"\s*\[\d+\]\s*", " ", item).strip()
        item = re.sub(r"\s*\.{3,}\s*$", ".", item)
        item = re.sub(r"\s*…\s*$", ".", item)
        if item and not _is_garbage_summary_line(item):
            cleaned.append(item[:500])

    good = [c for c in cleaned if not _is_garbage_summary_line(c)]
    if not good:
        return synthesize_natural_summary(question, key_changes)
    if any(_is_garbage_summary_line(c) for c in good):
        return synthesize_natural_summary(question, key_changes)
    if good[0].startswith("Across ") and "document(s)" in good[0]:
        return synthesize_natural_summary(question, key_changes)
    if key_changes and len(good) < 2:
        return synthesize_natural_summary(question, key_changes)
    return good[:6]


def to_plain_text(value: str | None) -> str:
    """Strip markdown/HTML markers so UI always shows normal text."""
    if not value:
        return ""
    text = str(value)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def structured_to_plain_text(structured: dict[str, Any]) -> str:
    """Build a plain-text fallback from structured answer (no markdown headings)."""
    lines: list[str] = []
    summary = structured.get("summary") or []
    if summary:
        lines.append("Quick summary")
        for item in summary:
            lines.append(f"- {to_plain_text(str(item))}")
        lines.append("")
    key_changes = structured.get("key_changes") or []
    if key_changes:
        lines.append("Key changes")
        for i, change in enumerate(key_changes, start=1):
            title = to_plain_text((change or {}).get("title") or "")
            desc = to_plain_text((change or {}).get("description") or "")
            cites = (change or {}).get("citation_indices") or []
            cite_str = "".join(f"[{c}]" for c in cites)
            bit = f"{i}. {title}".strip()
            if desc:
                bit = f"{bit} — {desc}"
            if cite_str:
                bit = f"{bit} {cite_str}"
            lines.append(bit)
        lines.append("")
    highlights = structured.get("highlights") or []
    if highlights:
        lines.append("Notable details")
        for h in highlights:
            text = to_plain_text((h or {}).get("text") or "")
            cites = (h or {}).get("citation_indices") or []
            cite_str = "".join(f"[{c}]" for c in cites)
            lines.append(f"- {text} {cite_str}".rstrip())
        lines.append("")
    caveat = structured.get("caveat")
    if caveat:
        lines.append(to_plain_text(str(caveat)))
        lines.append("")
    prose = structured.get("markdown")
    if prose and str(prose).strip():
        lines.append(to_plain_text(str(prose)))
    return "\n".join(lines).strip()


# Back-compat alias used by older imports/tests
def structured_to_markdown(structured: dict[str, Any]) -> str:
    return structured_to_plain_text(structured)


@dataclass
class LlmResult:
    text: str
    cited_indices: list[int] = field(default_factory=list)
    provider: str = "MOCK"
    model_name: str = "mock-gemini"
    input_tokens: int = 0
    output_tokens: int = 0
    structured: dict[str, Any] | None = None


def _clean_indices(raw: Any, available_count: int) -> list[int]:
    if not isinstance(raw, list):
        return []
    claimed: list[int] = []
    for item in raw:
        try:
            claimed.append(int(item))
        except (TypeError, ValueError):
            continue
    return validate_citation_indices(claimed, available_count)


def parse_structured_answer(
    raw: Any,
    *,
    available_count: int,
    question: str = "",
) -> tuple[dict[str, Any] | None, list[int]]:
    """Normalize provider JSON into a structured answer + cited indices."""
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract first JSON object
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return None, []
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None, []

    if not isinstance(data, dict):
        return None, []

    answer_type = str(data.get("answer_type") or "GENERAL").upper()
    if answer_type not in ANSWER_TYPES:
        answer_type = "GENERAL"

    summary_raw = data.get("summary") or []
    summary: list[str] = []
    for s in summary_raw:
        item = to_plain_text(str(s))
        item = re.sub(r"\s*\[\d+\]\s*", " ", item).strip()
        item = re.sub(r"\s*\.{3,}\s*$", ".", item)
        item = re.sub(r"\s*…\s*$", ".", item)
        if item:
            summary.append(item[:500])
        if len(summary) >= 8:
            break

    key_changes: list[dict[str, Any]] = []
    all_cited: list[int] = []
    for item in data.get("key_changes") or []:
        if not isinstance(item, dict):
            continue
        title = to_plain_text(str(item.get("title") or ""))
        title = _clean_title_label(title) or title
        if not title:
            continue
        indices = _clean_indices(item.get("citation_indices"), available_count)
        all_cited.extend(indices)
        key_changes.append(
            {
                "title": title[:300],
                "description": (
                    _clean_snippet_for_description(str(item.get("description") or ""), 800)
                    or to_plain_text(str(item.get("description") or ""))[:800]
                ),
                "citation_indices": indices,
            }
        )

    highlights: list[dict[str, Any]] = []
    for item in data.get("highlights") or []:
        if isinstance(item, str):
            text = to_plain_text(item)
            indices: list[int] = []
        elif isinstance(item, dict):
            text = to_plain_text(str(item.get("text") or ""))
            indices = _clean_indices(item.get("citation_indices"), available_count)
        else:
            continue
        if not text:
            continue
        all_cited.extend(indices)
        # Also pick up inline [n] in text, then strip them from display text
        inline = [int(x) for x in re.findall(r"\[(\d+)\]", text)]
        all_cited.extend(inline)
        if not indices and inline:
            indices = validate_citation_indices(inline, available_count)
        text = re.sub(r"\s*\[\d+\]\s*", " ", text).strip()
        highlights.append({"text": text[:1000], "citation_indices": indices})

    compare = data.get("compare")
    if compare is not None and not isinstance(compare, dict):
        compare = None

    caveat = data.get("caveat")
    caveat_s = to_plain_text(str(caveat)) if caveat else None

    markdown = data.get("markdown")
    markdown_s = to_plain_text(str(markdown)) if markdown else None

    # Collect citations from prose too
    if markdown_s:
        all_cited.extend(int(x) for x in re.findall(r"\[(\d+)\]", markdown_s))
        markdown_s = re.sub(r"\s*\[\d+\]\s*", " ", markdown_s).strip() or None

    cited = validate_citation_indices(all_cited, available_count)
    if answer_type == "NO_SOURCE":
        cited = []

    summary = finalize_summary(summary, question, key_changes)

    structured: dict[str, Any] = {
        "answer_type": answer_type,
        "summary": summary,
        "key_changes": key_changes[:20],
        "highlights": highlights[:20],
        "compare": compare,
        "caveat": caveat_s or None,
        "markdown": markdown_s or None,
    }

    return structured, cited


def no_source_structured(message: str) -> dict[str, Any]:
    return {
        "answer_type": "NO_SOURCE",
        "summary": [],
        "key_changes": [],
        "highlights": [],
        "compare": None,
        "caveat": None,
        "markdown": message,
    }


def no_source_notebooklm(message: str) -> dict[str, Any]:
    return {
        "format": "notebooklm",
        "answer_type": "NO_SOURCE",
        "answer": message,
        "sources": [],
    }


def _parse_json_payload(raw: Any) -> dict[str, Any] | None:
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return data if isinstance(data, dict) else None


def parse_notebooklm_answer(
    raw: Any,
    *,
    available_count: int,
    hits: list[RetrievalHit],
) -> tuple[dict[str, Any] | None, list[int]]:
    data = _parse_json_payload(raw)
    if not data:
        return None, []

    answer = to_plain_text(str(data.get("answer") or "")).strip()
    sources_out: list[dict[str, Any]] = []
    cited: list[int] = []

    for item in data.get("sources") or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if idx < 1 or idx > available_count:
            continue
        hit = hits[idx - 1]
        snippet = to_plain_text(str(item.get("quoted_snippet") or ""))[:500]
        if not snippet:
            snippet = _clean_snippet_for_description(hit.content or hit.snippet, 200)
        sources_out.append(
            {
                "id": idx,
                "page_title": to_plain_text(str(item.get("page_title") or hit.title))[:300],
                "section_heading": to_plain_text(
                    str(item.get("section_heading") or hit.section_heading or hit.title)
                )[:300],
                "source_url": str(item.get("source_url") or hit.source_url or "")[:1000] or None,
                "quoted_snippet": snippet,
            }
        )
        cited.append(idx)

    inline = [int(x) for x in re.findall(r"\[(\d+)\]", answer)]
    cited = validate_citation_indices(cited + inline, available_count)

    if not answer:
        return None, cited

    no_source_markers = (
        "không tìm thấy thông tin",
        "could not find",
        "no information",
    )
    answer_type = "NO_SOURCE" if any(m in answer.lower() for m in no_source_markers) else "GENERAL"
    if answer_type == "NO_SOURCE":
        cited = []

    if not sources_out and cited:
        for idx in cited:
            hit = hits[idx - 1]
            sources_out.append(
                {
                    "id": idx,
                    "page_title": hit.title,
                    "section_heading": hit.section_heading or hit.title,
                    "source_url": hit.source_url,
                    "quoted_snippet": _clean_snippet_for_description(
                        hit.content or hit.snippet, 200
                    ),
                }
            )

    structured: dict[str, Any] = {
        "format": "notebooklm",
        "answer_type": answer_type,
        "answer": answer,
        "sources": sources_out,
    }
    return structured, cited


def build_llm_context_block(index: int, hit: RetrievalHit) -> str:
    parent = (hit.parent_section or hit.content or hit.snippet or "").strip()
    if len(parent) > 2000:
        parent = parent[:2000] + "…"
    excerpt = (hit.content or hit.snippet or "").strip()
    lines = [
        f"[{index}] Page: {hit.title}",
        f"Section: {hit.section_heading or hit.heading_path or hit.title}",
    ]
    if hit.source_url:
        lines.append(f"URL: {hit.source_url}")
    lines.append("--- Parent section ---")
    lines.append(parent or excerpt)
    if excerpt and excerpt != parent:
        lines.append("--- Excerpt ---")
        lines.append(excerpt)
    return "\n".join(lines)


class LlmProvider(Protocol):
    async def generate(self, question: str, sources: list[RetrievalHit]) -> LlmResult: ...


class MockGeminiProvider:
    """Demo provider: NotebookLM-style answers from retrieved chunks."""

    async def generate(self, question: str, sources: list[RetrievalHit]) -> LlmResult:
        if not sources:
            msg = (
                "Tôi không tìm thấy thông tin này trong tài liệu hiện có. "
                "Hãy thử từ khóa cụ thể hơn hoặc chọn thêm Space."
            )
            structured = no_source_notebooklm(msg)
            return LlmResult(
                text=msg,
                cited_indices=[],
                provider="MOCK",
                model_name="mock-gemini",
                structured=structured,
            )

        cited: list[int] = []
        source_rows: list[dict[str, Any]] = []
        answer_bits: list[str] = []

        vi = _question_looks_vietnamese(question)
        if vi:
            answer_bits.append(
                f"Dựa trên {min(len(sources), 3)} đoạn tài liệu liên quan trong Space đã chọn:"
            )
        else:
            answer_bits.append(
                f"Based on {min(len(sources), 3)} relevant passages in the selected Spaces:"
            )

        for i, hit in enumerate(sources[:5], start=1):
            cited.append(i)
            snippet = _clean_snippet_for_description(hit.content or hit.snippet, 180)
            title = _clean_title_label(hit.title) or hit.title
            section = hit.section_heading or title
            if snippet:
                answer_bits.append(f"{snippet} [{i}]")
            else:
                answer_bits.append(f"{title} [{i}]")
            source_rows.append(
                {
                    "id": i,
                    "page_title": title[:300],
                    "section_heading": section[:300],
                    "source_url": hit.source_url,
                    "quoted_snippet": snippet or title[:200],
                }
            )

        answer = " ".join(answer_bits)
        structured = {
            "format": "notebooklm",
            "answer_type": "GENERAL",
            "answer": answer,
            "sources": source_rows,
        }
        return LlmResult(
            text=answer,
            cited_indices=cited,
            provider="MOCK",
            model_name="mock-gemini",
            input_tokens=max(1, len(question) // 4),
            output_tokens=max(1, len(answer) // 4),
            structured=structured,
        )


class GeminiProvider:
    def __init__(self, api_key: str, *, model: str | None = None) -> None:
        self.api_key = api_key
        self.preferred_model = model or getattr(settings, "gemini_model", None) or DEFAULT_GEMINI_MODEL
        self.model = self.preferred_model

    async def generate(self, question: str, sources: list[RetrievalHit]) -> LlmResult:
        if not sources:
            msg = "Tôi không tìm thấy thông tin này trong tài liệu hiện có."
            structured = no_source_notebooklm(msg)
            return LlmResult(
                text=msg,
                cited_indices=[],
                provider="GEMINI",
                model_name=self.model,
                structured=structured,
            )

        numbered = [build_llm_context_block(i, hit) for i, hit in enumerate(sources, start=1)]
        prompt = (
            f"{NOTEBOOKLM_JSON_INSTRUCTION}\n\n"
            f"Context:\n{chr(10).join(numbered)}\n\n"
            f"Câu hỏi: {question.strip()}\n"
        )

        try:
            data, model = await gemini_generate_best(
                self.api_key,
                prompt,
                preferred_model=self.preferred_model,
                json_mode=True,
            )
        except RuntimeError as exc:
            if "quota" in str(exc).lower() or "429" in str(exc):
                raise RuntimeError("Gemini quota exceeded") from exc
            raise
        self.model = model

        text = ""
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:  # noqa: BLE001
            text = json.dumps(data)[:500]

        structured, cited = parse_notebooklm_answer(
            text, available_count=len(sources), hits=sources
        )
        if structured is None:
            structured, cited = parse_structured_answer(
                text, available_count=len(sources), question=question
            )
        if structured is None:
            claimed = [int(x) for x in re.findall(r"\[(\d+)\]", text)]
            cited = validate_citation_indices(claimed, len(sources))
            fallback_text = (
                to_plain_text(text) or "Tôi không tìm thấy thông tin này trong tài liệu hiện có."
            )
            usage = data.get("usageMetadata") or {}
            return LlmResult(
                text=fallback_text,
                cited_indices=cited,
                provider="GEMINI",
                model_name=model,
                input_tokens=int(usage.get("promptTokenCount") or 0),
                output_tokens=int(usage.get("candidatesTokenCount") or 0),
                structured=None,
            )

        readable = structured.get("answer") if structured.get("format") == "notebooklm" else (
            structured_to_plain_text(structured)
            or to_plain_text(str(structured.get("markdown") or ""))
            or to_plain_text(text)
        )
        usage = data.get("usageMetadata") or {}
        return LlmResult(
            text=readable,
            cited_indices=cited,
            provider="GEMINI",
            model_name=model,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
            structured=structured,
        )


async def stream_text(text: str, *, chunk_size: int = 48) -> AsyncIterator[str]:
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
