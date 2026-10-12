from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ingestion.embeddings import embed_texts
from app.models.document import (
    INDEXABLE_DOCUMENT_TYPES,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.models.space import Space, SpaceRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService
from app.rag.fusion import cosine_similarity, embedding_is_usable, rrf_fuse
from app.rag.query_rewrite import rewrite_query_variants, should_rewrite_query
from app.rag.rerank import rerank_hits
from app.rag.search_tokens import (
    extract_precision_phrases,
    extract_search_tokens,
)
from app.rag.types import RetrievalHit

ACTIVE_PAGE = (DocumentStatus.READY, DocumentStatus.DRAFT)


def _is_postgres() -> bool:
    return "postgresql" in settings.database_url


def _meta_str(meta: dict[str, Any] | None, key: str) -> str | None:
    if not meta:
        return None
    value = meta.get(key)
    if value is None:
        return None
    text_val = str(value).strip()
    return text_val or None


def _hit_from_row(
    chunk: DocumentChunk,
    doc: Document,
    *,
    score: float,
    term: str,
) -> RetrievalHit:
    meta = chunk.metadata_json or {}
    content = chunk.content or ""
    section_heading = _meta_str(meta, "section_heading") or (chunk.heading_path or doc.title or "")
    return RetrievalHit(
        chunk_id=chunk.id,
        document_id=doc.id,
        space_id=doc.space_id,
        title=doc.title or "",
        snippet=_snippet(content, term[:40]),
        score=score,
        chunk_index=chunk.chunk_index,
        section_heading=section_heading,
        source_url=_meta_str(meta, "source_url") or doc.external_url,
        space_key=_meta_str(meta, "space_key"),
        parent_section=_meta_str(meta, "parent_section") or content,
        content=content,
        heading_path=chunk.heading_path or doc.title or "",
        source_id=chunk.source_id,
        citation_label=_meta_str(meta, "citation_label") or None,
    )


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def distinctive_search_tokens(tokens: list[str], *, max_keep: int = 5) -> list[str]:
    """Prefer longer tokens so common short Vietnamese syllables do not flood OR search."""
    cleaned = [t for t in tokens if t and t.strip()]
    if not cleaned:
        return []
    ranked = sorted(cleaned, key=lambda t: (-len(t), t.lower()))
    out: list[str] = []
    seen: set[str] = set()
    for tok in ranked:
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
        if len(out) >= max_keep:
            break
    return out


_DELIVERY_TERMS = ("giao", "phiếu", "phieu", "delivery", "shipment")
# Prefer multi-word delivery markers — bare "giao" matches "Giao diện".
_DELIVERY_PHRASES = (
    "phiếu giao",
    "phieu giao",
    "đơn giao",
    "don giao",
    "giao hàng",
    "giao hang",
    "delivery note",
    "delivery order",
)
# Titles that only mention operational "giao hàng" (APP) must not pin over sync docs.
_DELIVERY_NOTE_PHRASES = (
    "phiếu giao",
    "phieu giao",
    "delivery note",
)
# Query meta words that should not drive AND filters (they exclude the right page).
_META_SEARCH_TOKENS = {
    "mapping",
    "map",
    "bảng",
    "bang",
    "trạng",
    "thái",
    "thai",
    "giữa",
    "giua",
    "status",
    "table",
    "sync",
}


def text_has_delivery_note(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _DELIVERY_NOTE_PHRASES)


def text_has_delivery_intent(text: str) -> bool:
    t = (text or "").lower()
    if any(p in t for p in _DELIVERY_PHRASES):
        return True
    return any(x in t for x in ("phiếu", "phieu", "delivery", "shipment"))


def query_wants_delivery(tokens: list[str], term: str = "") -> bool:
    tokens_l = [t.lower() for t in tokens]
    blob = f"{' '.join(tokens_l)} {(term or '').lower()}"
    if any(p in blob for p in _DELIVERY_PHRASES):
        return True
    if any(t in blob for t in ("phiếu", "phieu", "delivery", "shipment")):
        return True
    # "đơn giao hàng" / "... với đơn giao" — not "giao diện"
    if "giao" in blob and "diện" not in blob and "dien" not in blob and "interface" not in blob:
        return any(t in blob for t in ("hàng", "hang", "đơn", "don", "bán", "ban"))
    return False


def query_wants_sales(tokens: list[str]) -> bool:
    blob = " ".join(t.lower() for t in tokens)
    return any(t in blob for t in ("bán", "ban", "sales"))


def title_search_patterns(term: str, tokens: list[str]) -> list[str]:
    """Build literal title phrases used for the title retrieval channel."""
    patterns: list[str] = []
    cleaned = " ".join((term or "").split())
    if len(cleaned) >= 4:
        patterns.append(cleaned)
    stripped = re.sub(r"^\[[^\]]+\]\s*", "", cleaned).strip()
    if stripped and stripped.lower() not in {p.lower() for p in patterns}:
        patterns.append(stripped)
    # Pull bracketed page titles out of chatty follow-ups
    # e.g. "Có trong page này [Enhance] Đồng bộ …"
    for m in re.finditer(r"\[[^\]]+\]\s*[^\[\]]{8,120}", cleaned):
        frag = m.group(0).strip()
        if frag.lower() not in {p.lower() for p in patterns}:
            patterns.append(frag)
    # Prefer contiguous query spans that look like page titles (not token-sorted noise).
    # Drop leading instructional verbs so the remaining noun phrase can match.
    intent = re.sub(
        r"^(mô tả|tóm tắt|tóm|tắt|mô|tả|describe|summarize|summary|explain|liệt kê)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    intent = re.sub(
        r"^(mô tả|tóm tắt|tóm|tắt|mô|tả|describe|summarize|summary|explain|liệt kê)\s+",
        "",
        intent,
        flags=re.IGNORECASE,
    ).strip()
    if len(intent) >= 12 and intent.lower() not in {p.lower() for p in patterns}:
        patterns.append(intent)
    return patterns


def is_literal_title_match(title: str, patterns: list[str], *, min_len: int = 10) -> bool:
    """True when a query phrase is a contiguous substring of the document title."""
    title_l = (title or "").lower()
    if not title_l:
        return False
    for pat in patterns:
        if len(pat) < min_len:
            continue
        if pat.lower() in title_l:
            return True
        # Also accept when the title is contained in a chatty "it's in this page X" query.
        if len(title_l) >= min_len and title_l in pat.lower():
            return True
    return False


def is_strong_title_hit(
    title: str,
    *,
    term: str,
    tokens: list[str],
    score: float,
) -> bool:
    """Pin titles that literally match the query, or clearly match sales↔delivery intent.

    Token-overlap alone on SAP-style 'Đồng bộ đơn hàng' must not pin — but a title that
    pairs sales + delivery-note phrasing should win for mapping/status questions that
    never quote the page name.
    """
    patterns = title_search_patterns(term, tokens)
    title_l = (title or "").lower()
    wants_del = query_wants_delivery(tokens, term)
    wants_sales = query_wants_sales(tokens)

    if is_literal_title_match(title, patterns):
        if wants_del and not text_has_delivery_intent(title_l):
            return False
        return score >= 60.0

    # Domain-strong: prefer delivery-note sync pages (phiếu giao) over APP "giao hàng".
    if (
        wants_del
        and wants_sales
        and text_has_delivery_note(title_l)
        and ("bán" in title_l or "ban" in title_l or "sales" in title_l)
        and score >= 70.0
    ):
        return True
    if (
        wants_del
        and wants_sales
        and ("đồng bộ" in title_l or "dong bo" in title_l or "sync" in title_l)
        and text_has_delivery_intent(title_l)
        and ("bán" in title_l or "ban" in title_l or "sales" in title_l)
        and score >= 100.0
    ):
        return True
    return False


def score_keyword_match(
    *,
    title: str,
    heading: str,
    content: str,
    tokens: list[str],
    title_boost: float = 0.0,
) -> tuple[float, int]:
    tokens_l = [t.lower() for t in tokens]
    title_l = (title or "").lower()
    heading_l = (heading or "").lower()
    content_l = (content or "").lower()
    score = title_boost
    matched = 0
    for tok in tokens_l:
        if tok in title_l:
            score += 4.0
            matched += 1
        elif tok in heading_l:
            score += 3.0
            matched += 1
        elif tok in content_l:
            score += 1.5
            matched += 1
    # Prefer pages whose title covers many query tokens.
    if tokens_l:
        title_hits = sum(1 for tok in tokens_l if tok in title_l)
        score += title_hits * 2.0
        if title_hits >= max(2, len(tokens_l) // 2):
            score += 20.0
    # Multi-word phrase hits are high-precision (e.g. "tài khoản", "phiếu giao").
    for tok in tokens_l:
        if " " not in tok:
            continue
        if tok in title_l:
            score += 35.0
        elif tok in heading_l:
            score += 22.0
        elif tok in content_l:
            score += 14.0
    # Domain pair: sales order + delivery note questions.
    wants_delivery = query_wants_delivery(tokens)
    wants_sales = query_wants_sales(tokens)
    title_delivery = text_has_delivery_intent(title_l)
    title_note = text_has_delivery_note(title_l)
    if wants_delivery and title_note:
        score += 28.0
    elif wants_delivery and title_delivery:
        score += 12.0
    if wants_delivery and wants_sales and title_note and ("bán" in title_l or "ban" in title_l):
        score += 40.0
    elif wants_delivery and wants_sales and title_delivery and ("bán" in title_l or "ban" in title_l):
        score += 18.0
    if wants_delivery and not title_delivery and not text_has_delivery_intent(heading_l):
        score -= 8.0
    # Prefer sync/mapping pages when the question asks for status mapping.
    blob = " ".join(tokens_l)
    if any(x in blob for x in ("mapping", "đồng", "bộ", "trạng", "thái")):
        if "đồng bộ" in title_l or "mapping" in title_l:
            score += 25.0
        if title_l.startswith("[app]") or title_l.startswith("[portal] -"):
            score -= 15.0
    return score, matched


class RetrievalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)

    async def search(
        self,
        user: User,
        workspace_id: UUID,
        query: str,
        *,
        space_ids: list[UUID] | None = None,
        source_ids: list[UUID] | None = None,
        limit: int | None = None,
        api_key: str | None = None,
        preferred_model: str | None = None,
    ) -> list[RetrievalHit]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        term = (query or "").strip()
        if len(term) < 2:
            return []

        allowed = await self._allowed_space_ids(user, workspace_id, space_ids)
        if not allowed:
            return []

        final_limit = limit or settings.ask_rerank_top_k
        pool_size = max(settings.ask_hybrid_pool_size, final_limit)

        queries = [term]
        if api_key and should_rewrite_query(term):
            variants = await rewrite_query_variants(
                api_key, term, preferred_model=preferred_model
            )
            queries.extend(variants)

        ranked_lists: list[list[UUID]] = []
        hit_map: dict[UUID, RetrievalHit] = {}
        for q in queries:
            hits = await self._hybrid_search(
                workspace_id,
                allowed,
                q,
                limit=pool_size,
                source_ids=source_ids,
            )
            ranked_lists.append([h.chunk_id for h in hits])
            for hit in hits:
                existing = hit_map.get(hit.chunk_id)
                if existing is None or hit.score > existing.score:
                    hit_map[hit.chunk_id] = hit

        if not ranked_lists:
            return []

        if len(ranked_lists) == 1:
            merged = list(hit_map.values())
            merged.sort(key=lambda h: -h.score)
        else:
            fused_scores = rrf_fuse(ranked_lists)
            merged = [
                RetrievalHit(
                    chunk_id=hit_map[cid].chunk_id,
                    document_id=hit_map[cid].document_id,
                    space_id=hit_map[cid].space_id,
                    title=hit_map[cid].title,
                    snippet=hit_map[cid].snippet,
                    score=score,
                    chunk_index=hit_map[cid].chunk_index,
                    section_heading=hit_map[cid].section_heading,
                    source_url=hit_map[cid].source_url,
                    space_key=hit_map[cid].space_key,
                    parent_section=hit_map[cid].parent_section,
                    content=hit_map[cid].content,
                    heading_path=hit_map[cid].heading_path,
                )
                for cid, score in sorted(fused_scores.items(), key=lambda x: -x[1])
                if cid in hit_map
            ]

        diversified = self._diversify(merged, pool_size)
        if api_key:
            return await rerank_hits(
                api_key,
                term,
                diversified,
                top_k=final_limit,
                preferred_model=preferred_model,
            )
        return diversified[:final_limit]

    async def _hybrid_search(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        term: str,
        *,
        limit: int,
        source_ids: list[UUID] | None = None,
    ) -> list[RetrievalHit]:
        tokens = extract_search_tokens(term)
        if not tokens:
            return []
        ambient = await self._ambient_token_set(allowed)
        if ambient:
            filtered = [t for t in tokens if t.lower() not in ambient]
            if filtered:
                tokens = filtered

        title_hits = await self._title_search(
            workspace_id, allowed, tokens, term, limit=limit
        )
        keyword_hits = await self._keyword_search(
            workspace_id, allowed, tokens, term, limit=limit
        )
        vector_hits = await self._vector_search(
            workspace_id, allowed, term, limit=limit, source_ids=source_ids
        )

        if source_ids:
            allowed_src = set(source_ids)

            def _src_ok(h: RetrievalHit) -> bool:
                return h.source_id is not None and h.source_id in allowed_src

            title_hits = [h for h in title_hits if _src_ok(h)]
            keyword_hits = [h for h in keyword_hits if _src_ok(h)]
            vector_hits = [h for h in vector_hits if _src_ok(h)]

        # Literal phrase matches pin hard; domain sales↔delivery titles also pin.
        # Always fuse title channel once so high-scoring title hits are not dropped
        # when keyword AND is skewed by meta tokens like "mapping".
        strong_title = [
            h
            for h in title_hits
            if is_strong_title_hit(h.title, term=term, tokens=tokens, score=h.score)
        ]
        ranked_lists: list[list[RetrievalHit]] = []
        if title_hits:
            ranked_lists.append(title_hits)
        if strong_title:
            ranked_lists.append(strong_title)
            ranked_lists.append(strong_title)
        if keyword_hits:
            ranked_lists.append(keyword_hits)
            # Keyword is the reliable channel on SQLite/demo (no real BM25/ANN).
            ranked_lists.append(keyword_hits)
        if vector_hits:
            ranked_lists.append(vector_hits)
        if not ranked_lists:
            return []
        if len(ranked_lists) == 1:
            return self._diversify(ranked_lists[0], limit)

        fused = self._fuse_many(ranked_lists, limit=max(limit * 2, 16))
        if strong_title:
            pinned_ids = {h.chunk_id for h in strong_title[:6]}
            head = [h for h in strong_title if h.chunk_id in pinned_ids][:6]
            rest = [h for h in fused if h.chunk_id not in pinned_ids]
            return self._diversify(head + rest, limit)
        return self._diversify(fused, limit)

    async def _title_search(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        tokens: list[str],
        term: str,
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        """Strong channel: match document titles to the query / distinctive phrases."""
        patterns = title_search_patterns(term, tokens)
        distinctive = distinctive_search_tokens(tokens, max_keep=6)

        docs_by_id: dict[UUID, Document] = {}

        # 0) Domain seed: sales + delivery-note titles (avoids OR+LIMIT missing the page
        # when tokens like "hàng"/"giao" flood the candidate set).
        if query_wants_delivery(tokens, term) and query_wants_sales(tokens):
            delivery_title = or_(
                Document.title.like("%phiếu giao%", escape="\\"),
                Document.title.like("%phieu giao%", escape="\\"),
                Document.title.like("%đơn giao%", escape="\\"),
                Document.title.like("%don giao%", escape="\\"),
                Document.title.like("%giao hàng%", escape="\\"),
                Document.title.like("%giao hang%", escape="\\"),
                Document.title.like("%delivery%", escape="\\"),
            )
            sales_title = or_(
                Document.title.like("%bán%", escape="\\"),
                Document.title.like("%ban%", escape="\\"),
                Document.title.like("%sales%", escape="\\"),
            )
            result = await self.db.execute(
                select(Document)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    delivery_title,
                    sales_title,
                )
                .limit(40)
            )
            for doc in result.scalars().all():
                docs_by_id[doc.id] = doc

        # 1) Exact-ish phrase matches first (must not be drowned by OR+LIMIT).
        for pat in patterns:
            if len(pat) < 8:
                continue
            escaped = _escape_like(pat)
            result = await self.db.execute(
                select(Document)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    Document.title.like(f"%{escaped}%", escape="\\"),
                )
                .limit(30)
            )
            for doc in result.scalars().all():
                docs_by_id[doc.id] = doc

        # 2) Broaden with distinctive token overlap on titles.
        token_filters = []
        for tok in distinctive[:5]:
            escaped = _escape_like(tok)
            token_filters.append(Document.title.like(f"%{escaped}%", escape="\\"))
        if token_filters:
            result = await self.db.execute(
                select(Document)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    or_(*token_filters),
                )
                .limit(120)
            )
            for doc in result.scalars().all():
                docs_by_id.setdefault(doc.id, doc)

        if not docs_by_id:
            return []

        scored_docs: list[tuple[float, Document]] = []
        for doc in docs_by_id.values():
            title_l = (doc.title or "").lower()
            hit_count = sum(1 for t in tokens if t.lower() in title_l)
            phrase_hit = is_literal_title_match(doc.title or "", patterns, min_len=8)
            if not phrase_hit and hit_count < max(2, min(4, max(len(tokens) // 2, 2))):
                continue
            boost = 80.0 if phrase_hit else 40.0
            scored_docs.append((boost + hit_count * 5.0, doc))
        scored_docs.sort(key=lambda row: -row[0])
        if not scored_docs:
            return []
        kept = [doc for _score, doc in scored_docs[:20]]

        doc_ids = [d.id for d in kept]
        result = await self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.document_id.in_(doc_ids))
        )
        hits: list[RetrievalHit] = []
        for chunk, doc in result.all():
            phrase_hit = is_literal_title_match(doc.title or "", patterns, min_len=8)
            score, matched = score_keyword_match(
                title=doc.title or "",
                heading=chunk.heading_path or "",
                content=chunk.content or "",
                tokens=tokens,
                title_boost=80.0 if phrase_hit else 40.0,
            )
            if matched == 0 and score < 40:
                continue
            hits.append(
                _hit_from_row(
                    chunk,
                    doc,
                    score=score,
                    term=tokens[0] if tokens else term[:40],
                )
            )
        hits.sort(key=lambda h: (-h.score, h.chunk_index, h.title.lower()))
        return hits[: max(limit * 4, 40)]
    async def _keyword_search(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        tokens: list[str],
        term: str,
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        if _is_postgres():
            fts = await self._keyword_search_fts(
                workspace_id, allowed, term, limit=limit
            )
            if fts:
                return fts
        return await self._keyword_search_like(
            workspace_id, allowed, tokens, term, limit=limit
        )

    async def _keyword_search_fts(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        term: str,
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        bind = {
            "workspace_id": str(workspace_id),
            "allowed": [str(s) for s in allowed],
            "query": term,
            "lim": max(limit * 4, 40),
        }
        sql = text(
            """
            SELECT dc.id AS chunk_id,
                   ts_rank_cd(dc.search_vector, plainto_tsquery('simple', :query)) AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.workspace_id = CAST(:workspace_id AS uuid)
              AND dc.space_id = ANY(CAST(:allowed AS uuid[]))
              AND d.document_type IN ('PAGE', 'JIRA_ISSUE', 'SHEET', 'FILE', 'PRESENTATION')
              AND d.deleted_at IS NULL
              AND d.status IN ('READY', 'DRAFT')
              AND dc.search_vector @@ plainto_tsquery('simple', :query)
            ORDER BY rank DESC, d.updated_at DESC
            LIMIT :lim
            """
        )
        try:
            result = await self.db.execute(sql, bind)
            rows = result.all()
        except Exception:  # noqa: BLE001
            tokens = extract_search_tokens(term)
            return await self._keyword_search_like(
                workspace_id, allowed, tokens, term, limit=limit
            )

        if not rows:
            tokens = extract_search_tokens(term)
            return await self._keyword_search_like(
                workspace_id, allowed, tokens, term, limit=limit
            )

        chunk_ids = [row.chunk_id for row in rows]
        rank_by_id = {row.chunk_id: float(row.rank or 0.0) for row in rows}
        result = await self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(chunk_ids))
        )
        by_id: dict[UUID, RetrievalHit] = {}
        for chunk, doc in result.all():
            by_id[chunk.id] = _hit_from_row(
                chunk,
                doc,
                score=rank_by_id.get(chunk.id, 0.0),
                term=term,
            )
        hits = [by_id[cid] for cid in chunk_ids if cid in by_id]
        hits.sort(key=lambda h: -h.score)
        return hits

    async def _keyword_search_like(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        tokens: list[str],
        term: str,
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        distinctive = distinctive_search_tokens(tokens) or tokens
        # Prefer entity tokens (bán/giao) over meta words (mapping/bảng/trạng) for AND.
        # Otherwise pages that describe the sync without saying "mapping" are excluded.
        entity = [t for t in distinctive if t.lower() not in _META_SEARCH_TOKENS]
        if query_wants_delivery(tokens, term) and query_wants_sales(tokens):
            # Phrase tokens like "đơn bán hàng" do not equal "bán" — search inside them.
            blob = f"{' '.join(t.lower() for t in tokens)} {(term or '').lower()}"
            sales = "bán" if any(x in blob for x in ("bán", " ban", "sales")) else None
            if "phiếu" in blob or "phieu" in blob:
                delivery = "phiếu"
            elif "delivery" in blob or "shipment" in blob:
                delivery = "delivery"
            elif "giao" in blob:
                delivery = "giao"
            else:
                delivery = None
            required = [t for t in (sales, delivery) if t]
            if len(required) < 2:
                for t in entity:
                    if all(t.lower() != r.lower() for r in required):
                        required.append(t)
                    if len(required) >= 2:
                        break
            if len(required) < 2:
                required = distinctive[:2] if len(distinctive) >= 2 else distinctive[:1]
        elif len(entity) >= 2:
            required = entity[:2]
        else:
            required = distinctive[:2] if len(distinctive) >= 2 else distinctive[:1]
        # If the question mentions delivery-side terms, force one into the AND so
        # SAP/Tiktok "đồng bộ đơn hàng" pages do not dominate.
        blob = f"{' '.join(t.lower() for t in (entity + distinctive + list(tokens)))} {(term or '').lower()}"
        if "phiếu" in blob or "phieu" in blob:
            delivery = "phiếu"
        elif "giao" in blob:
            delivery = "giao"
        elif "delivery" in blob or "shipment" in blob:
            delivery = "delivery"
        else:
            delivery = None
        if delivery and required and all(t.lower() != delivery.lower() for t in required):
            if len(required) >= 2:
                required = [required[0], delivery]
            else:
                required = [*required, delivery]
        optional = [t for t in distinctive if all(t.lower() != r.lower() for r in required)]

        def _tok_filters(tok: str) -> list:
            escaped = _escape_like(tok)
            pattern = f"%{escaped}%"
            return [
                DocumentChunk.content.like(pattern, escape="\\"),
                Document.title.like(pattern, escape="\\"),
                DocumentChunk.heading_path.like(pattern, escape="\\"),
            ]

        rows: list = []
        seen_chunk_ids: set[UUID] = set()

        # Seed by high-precision phrases only (e.g. "tài khoản", "phiếu giao").
        # Broader phrases like "đơn giao hàng" flood unrelated APP/portal pages.
        phrases = extract_precision_phrases(term)
        for phrase in phrases[:3]:
            escaped = _escape_like(phrase)
            pattern = f"%{escaped}%"
            seeded_phrase = await self.db.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    DocumentChunk.workspace_id == workspace_id,
                    DocumentChunk.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    or_(
                        DocumentChunk.content.like(pattern, escape="\\"),
                        Document.title.like(pattern, escape="\\"),
                        DocumentChunk.heading_path.like(pattern, escape="\\"),
                    ),
                )
                .limit(80)
            )
            for chunk, doc in seeded_phrase.all():
                if chunk.id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.id)
                rows.append((chunk, doc))

        # Seed chunks from sales↔delivery titles first so LIMIT cannot drop them.
        if query_wants_delivery(tokens, term) and query_wants_sales(tokens):
            delivery_title = or_(
                Document.title.like("%phiếu giao%", escape="\\"),
                Document.title.like("%phieu giao%", escape="\\"),
                Document.title.like("%đơn giao%", escape="\\"),
                Document.title.like("%giao hàng%", escape="\\"),
                Document.title.like("%delivery%", escape="\\"),
            )
            sales_title = or_(
                Document.title.like("%bán%", escape="\\"),
                Document.title.like("%ban%", escape="\\"),
                Document.title.like("%sales%", escape="\\"),
            )
            seeded = await self.db.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    DocumentChunk.workspace_id == workspace_id,
                    DocumentChunk.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    delivery_title,
                    sales_title,
                )
                .limit(80)
            )
            for chunk, doc in seeded.all():
                if chunk.id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.id)
                rows.append((chunk, doc))

        where_clauses = [
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.space_id.in_(allowed),
            Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
            Document.deleted_at.is_(None),
            Document.status.in_(ACTIVE_PAGE),
        ]
        for tok in required:
            where_clauses.append(or_(*_tok_filters(tok)))
        if optional:
            where_clauses.append(or_(*[f for tok in optional for f in _tok_filters(tok)]))

        result = await self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*where_clauses)
            .limit(max(limit * 40, 400))
        )
        for chunk, doc in result.all():
            if chunk.id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.id)
            rows.append((chunk, doc))

        # Fallback: if AND was too strict and seed found nothing, OR distinctive tokens.
        if not rows:
            token_filters = []
            for tok in distinctive:
                token_filters.extend(_tok_filters(tok))
            result = await self.db.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    DocumentChunk.workspace_id == workspace_id,
                    DocumentChunk.space_id.in_(allowed),
                    Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
                    Document.deleted_at.is_(None),
                    Document.status.in_(ACTIVE_PAGE),
                    or_(*token_filters),
                )
                .limit(max(limit * 40, 400))
            )
            for chunk, doc in result.all():
                if chunk.id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.id)
                rows.append((chunk, doc))

        hits: list[RetrievalHit] = []
        for chunk, doc in rows:
            score, matched = score_keyword_match(
                title=doc.title or "",
                heading=chunk.heading_path or "",
                content=chunk.content or "",
                tokens=tokens,
            )
            if matched == 0:
                continue
            snip_term = next(
                (
                    t
                    for t in tokens
                    if t.lower() in (chunk.content or "").lower()
                    or t.lower() in (doc.title or "").lower()
                ),
                tokens[0],
            )
            hits.append(_hit_from_row(chunk, doc, score=score, term=snip_term))

        hits.sort(key=lambda h: (-h.score, h.title.lower()))
        return hits

    async def _vector_search(
        self,
        workspace_id: UUID,
        allowed: list[UUID],
        term: str,
        *,
        limit: int,
        source_ids: list[UUID] | None = None,
    ) -> list[RetrievalHit]:
        query_vecs = await embed_texts([term])
        if not query_vecs or not embedding_is_usable(query_vecs[0]):
            return []
        query_vec = query_vecs[0]

        # Score all in-scope chunks — partial LIMIT without ORDER BY previously
        # dropped relevant pages in large spaces.
        filters = [
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.space_id.in_(allowed),
            Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
            Document.deleted_at.is_(None),
            Document.status.in_(ACTIVE_PAGE),
            DocumentChunk.embedding.is_not(None),
        ]
        if source_ids:
            filters.append(DocumentChunk.source_id.in_(source_ids))
        result = await self.db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*filters)
        )
        scored: list[tuple[float, DocumentChunk, Document]] = []
        for chunk, doc in result.all():
            vec = chunk.embedding
            if not embedding_is_usable(vec):
                continue
            sim = cosine_similarity(query_vec, vec)  # type: ignore[arg-type]
            if sim <= 0.02:
                continue
            scored.append((sim, chunk, doc))
        scored.sort(key=lambda row: -row[0])
        hits: list[RetrievalHit] = []
        for sim, chunk, doc in scored[: max(limit * 4, 32)]:
            hits.append(_hit_from_row(chunk, doc, score=sim, term=term[:40]))
        return hits

    def _fuse_many(
        self,
        ranked_lists: list[list[RetrievalHit]],
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        by_id: dict[UUID, RetrievalHit] = {}
        for ranked in ranked_lists:
            for h in ranked:
                by_id[h.chunk_id] = h
        fused_scores = rrf_fuse([[h.chunk_id for h in ranked] for ranked in ranked_lists])
        merged: list[RetrievalHit] = []
        for chunk_id, rrf_score in sorted(fused_scores.items(), key=lambda x: -x[1]):
            base = by_id[chunk_id]
            merged.append(
                RetrievalHit(
                    chunk_id=base.chunk_id,
                    document_id=base.document_id,
                    space_id=base.space_id,
                    title=base.title,
                    snippet=base.snippet,
                    score=rrf_score,
                    chunk_index=base.chunk_index,
                    section_heading=base.section_heading,
                    source_url=base.source_url,
                    space_key=base.space_key,
                    parent_section=base.parent_section,
                    content=base.content,
                    heading_path=base.heading_path,
                )
            )
        return self._diversify(merged, limit)

    def _fuse_hits(
        self,
        keyword_hits: list[RetrievalHit],
        vector_hits: list[RetrievalHit],
        *,
        limit: int,
    ) -> list[RetrievalHit]:
        return self._fuse_many([keyword_hits, vector_hits], limit=limit)

    def _diversify(self, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        out: list[RetrievalHit] = []
        per_doc: dict[UUID, int] = {}
        # Allow more chunks from a doc when its title clearly matches the query intent.
        for h in hits:
            n = per_doc.get(h.document_id, 0)
            max_per = 4 if h.score >= 40 else 2
            if n >= max_per:
                continue
            per_doc[h.document_id] = n + 1
            out.append(h)
            if len(out) >= limit:
                break
        return out

    async def _ambient_token_set(self, allowed: list[UUID]) -> set[str]:
        """Space-name tokens are noise when Ask AI is already scoped to that Space."""
        if not allowed:
            return set()
        result = await self.db.execute(select(Space).where(Space.id.in_(allowed)))
        ambient: set[str] = set()
        for space in result.scalars().all():
            for part in re.findall(
                r"[0-9A-Za-zÀ-ỹĐđ]{2,}", space.name or "", flags=re.UNICODE
            ):
                ambient.add(part.lower())
        return ambient

    async def _allowed_space_ids(
        self,
        user: User,
        workspace_id: UUID,
        space_ids: list[UUID] | None,
    ) -> list[UUID]:
        if space_ids:
            out: list[UUID] = []
            for sid in space_ids:
                try:
                    await self.permissions.require_space_access(sid, user.id, SpaceRole.VIEWER)
                    space = await self.permissions.require_space(sid)
                    if space.workspace_id == workspace_id:
                        out.append(sid)
                except Exception:  # noqa: BLE001
                    continue
            return out

        from app.models.space import Space, SpaceMembership, SpaceStatus

        result = await self.db.execute(
            select(Space.id)
            .join(
                SpaceMembership,
                (SpaceMembership.space_id == Space.id)
                & (SpaceMembership.user_id == user.id)
                & (SpaceMembership.revoked_at.is_(None)),
            )
            .where(
                Space.workspace_id == workspace_id,
                Space.deleted_at.is_(None),
                Space.status != SpaceStatus.DELETED,
            )
        )
        return list(result.scalars().all())


def _snippet(content: str, term: str, radius: int = 120) -> str:
    text_body = " ".join((content or "").split())
    if not text_body:
        return ""
    idx = text_body.lower().find(term.lower())
    if idx < 0:
        return text_body[: radius * 2] + ("…" if len(text_body) > radius * 2 else "")
    start = max(0, idx - radius)
    end = min(len(text_body), idx + len(term) + radius)
    out = text_body[start:end]
    if start > 0:
        out = "…" + out
    if end < len(text_body):
        out = out + "…"
    return out


def validate_citation_indices(
    claimed: list[int],
    available_count: int,
) -> list[int]:
    """Return 1-based citation indices that exist in the retrieved set."""
    valid: list[int] = []
    seen: set[int] = set()
    for idx in claimed:
        if not isinstance(idx, int):
            continue
        if idx < 1 or idx > available_count:
            continue
        if idx in seen:
            continue
        seen.add(idx)
        valid.append(idx)
    return valid
