from __future__ import annotations

import re

# Common Vietnamese + English function words — skip for retrieval tokens.
_STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "with",
    "from",
    "by",
    "as",
    "at",
    "it",
    "this",
    "that",
    "các",
    "của",
    "và",
    "là",
    "cho",
    "với",
    "trong",
    "trên",
    "được",
    "những",
    "một",
    "cái",
    "này",
    "khi",
    "có",
    "không",
    "về",
    "từ",
    "đến",
    "như",
    "để",
    "đã",
    "sẽ",
    "bị",
    "hay",
    "hoặc",
    "tôi",
    "bạn",
    "hãy",
    "giúp",
    "liệt",
    "kê",
    "tổng",
    "hợp",
    "tóm",
    "tắt",
    "nội",
    "dung",
    "thay",
    "đổi",
    "dự",
    "án",
    "mô",
    "tả",
    "page",
    "please",
    "list",
    "summarize",
    "summary",
    "what",
    "how",
    "why",
    "who",
    "which",
}

# Multi-word phrases that must stay intact (syllable split destroys them).
# Keep this list high-precision — broad phrases like "đơn giao hàng" match too many titles.
_KNOWN_PHRASES = (
    "mapping trạng thái",
    "tạo tài khoản",
    "đăng ký tài khoản",
    "tài khoản",
    "tai khoan",
    "phiếu giao hàng",
    "phiếu giao",
    "phieu giao",
    "nhân viên giao hàng",
    "white list",
    "whitelist",
)

# Only these are safe to AND/seed — same set as known phrases for now.
_HIGH_PRECISION_PHRASES = frozenset(_KNOWN_PHRASES)


def extract_search_phrases(query: str) -> list[str]:
    """Return known multi-word phrases present in the query (longest first)."""
    raw = (query or "").lower()
    if not raw:
        return []
    found: list[str] = []
    for phrase in sorted(_KNOWN_PHRASES, key=len, reverse=True):
        if phrase in raw and phrase not in found:
            # Skip shorter phrases fully covered by an already-found longer one.
            if any(phrase in longer for longer in found):
                continue
            found.append(phrase)
    return found


def extract_precision_phrases(query: str) -> list[str]:
    """High-precision phrases safe for AND filters / DB seeding."""
    return [p for p in extract_search_phrases(query) if p in _HIGH_PRECISION_PHRASES]


def extract_search_tokens(query: str, *, max_tokens: int = 12) -> list[str]:
    """Split a natural-language question into searchable tokens.

    Longer tokens are preferred so short Vietnamese syllables do not crowd out
    distinctive nouns (e.g. keep ``giao`` / ``hàng`` instead of only ``mô``/``tả``).
    Multi-word phrases are prepended so ``tài khoản`` is not lost as ``tài``+``khoản``.
    """
    raw = (query or "").strip()
    if not raw:
        return []
    phrases = extract_search_phrases(raw)
    tokens: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(phrase)
    parts = re.findall(r"[0-9A-Za-zÀ-ỹĐđ]{2,}", raw, flags=re.UNICODE)
    ordered = sorted(enumerate(parts), key=lambda item: (-len(item[1]), item[0]))
    for _idx, p in ordered:
        low = p.lower()
        if low in _STOPWORDS:
            continue
        # Skip syllables already covered by a kept phrase.
        if any(low in ph.lower().split() for ph in phrases):
            continue
        if low in seen:
            continue
        seen.add(low)
        tokens.append(p)
        if len(tokens) >= max_tokens:
            break
    if not tokens and len(raw) >= 2:
        tokens = [raw[:80]]
    return tokens
