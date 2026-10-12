from __future__ import annotations

PRESENTATION_JSON_INSTRUCTION = """You are a presentation designer. Create a slide deck ONLY from the numbered source passages below.
Do NOT invent facts. Every slide must cite at least one source index in source_indices.

Respond with ONLY a single JSON object (no markdown fences):
{
  "title": "Deck title",
  "slides": [
    {
      "title": "Short slide title",
      "bullets": ["point 1", "point 2"],
      "notes": "Optional speaker notes",
      "source_indices": [1, 2]
    }
  ]
}

Rules:
- 6–14 slides total.
- Logical flow: Title → Context/Problem → Main sections → Conclusion.
- Max 6 bullets per slide; each bullet is one concise idea.
- source_indices must reference valid source numbers from Context.
- Write in the SAME language as the source material (Vietnamese if sources are Vietnamese).
- If focus_prompt is provided, emphasize that theme without ignoring other key content.
"""

MINDMAP_JSON_INSTRUCTION = """You are a knowledge analyst. Build a hierarchical mind map ONLY from the numbered source passages below.
Do NOT invent concepts not supported by sources.

Respond with ONLY a single JSON object (no markdown fences):
{
  "root_label": "Central topic (short)",
  "nodes": [
    {
      "id": "n1",
      "label": "Short label",
      "parent_id": null,
      "source_index": 1
    },
    {
      "id": "n2",
      "label": "Child topic",
      "parent_id": "n1",
      "source_index": 2
    }
  ]
}

Rules:
- Exactly one root node with parent_id null (use id "root" or similar).
- Max depth 4 levels from root.
- 8–40 nodes total; labels are 2–6 words.
- source_index must be a valid source number for each node.
- Write labels in the SAME language as the source material.
"""

MAP_SUMMARIZE_INSTRUCTION = """Summarize the following document passage for later synthesis into slides or a mind map.
Keep key facts, names, and relationships. Output plain text only (no JSON), max 1200 words.
"""


def user_focus_block(focus_prompt: str | None) -> str:
    text = (focus_prompt or "").strip()
    if not text:
        return ""
    return (
        f"\nNgười dùng yêu cầu tập trung vào: {text}\n"
        "Hãy ưu tiên nội dung liên quan đến yêu cầu này khi tổng hợp, "
        "nhưng vẫn đảm bảo tính chính xác, chỉ dùng thông tin có trong nguồn tài liệu.\n"
    )


def presentation_prompt(context: str, *, focus_prompt: str | None = None) -> str:
    focus = user_focus_block(focus_prompt)
    return f"{PRESENTATION_JSON_INSTRUCTION}{focus}\nContext:\n{context}\n"


def mindmap_prompt(context: str, *, focus_prompt: str | None = None) -> str:
    focus = user_focus_block(focus_prompt)
    return f"{MINDMAP_JSON_INSTRUCTION}{focus}\nContext:\n{context}\n"


def map_summarize_prompt(title: str, content: str) -> str:
    return f"{MAP_SUMMARIZE_INSTRUCTION}\nDocument: {title}\n\n{content[:12000]}\n"


def regenerate_slide_prompt(
    context: str,
    *,
    slide_title: str,
    focus_prompt: str | None = None,
) -> str:
    focus = user_focus_block(focus_prompt)
    return (
        f"{PRESENTATION_JSON_INSTRUCTION}{focus}\n"
        f"Regenerate ONLY one slide to replace slide titled \"{slide_title}\".\n"
        f"Return JSON with a single slide in the slides array.\n\n"
        f"Context:\n{context}\n"
    )
