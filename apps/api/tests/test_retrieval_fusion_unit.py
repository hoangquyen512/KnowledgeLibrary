from app.rag.fusion import cosine_similarity, embedding_is_usable, rrf_fuse
from app.rag.retrieval import (
    distinctive_search_tokens,
    is_strong_title_hit,
    score_keyword_match,
)
from app.rag.search_tokens import extract_search_phrases, extract_search_tokens


def test_embedding_is_usable() -> None:
    assert not embedding_is_usable(None)
    assert not embedding_is_usable([0.0, 0.0, 0.0])
    assert embedding_is_usable([0.0, 0.1, 0.0])


def test_cosine_similarity_identical() -> None:
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_rrf_fuse_prefers_both_lists() -> None:
    from uuid import uuid4

    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    scores = rrf_fuse([[a, b, c], [b, d, a]])
    assert scores[b] > scores[c]
    assert scores[a] > scores[d]


def test_distinctive_search_tokens_prefers_longer() -> None:
    tokens = ["bộ", "Đơn", "Enhance", "Phiếu", "Hàng"]
    out = distinctive_search_tokens(tokens, max_keep=3)
    assert out[0] == "Enhance"
    assert "Phiếu" in out


def test_extract_keeps_account_phrase() -> None:
    tokens = extract_search_tokens("tạo tài khoản ecom")
    assert tokens[0] == "tạo tài khoản"
    assert "ecom" in [t.lower() for t in tokens]
    assert extract_search_phrases("tạo tài khoản ecom") == ["tạo tài khoản"]


def test_score_keyword_match_boosts_title_overlap() -> None:
    score, matched = score_keyword_match(
        title="[Enhance] Đồng bộ Đơn Hàng Bán với Phiếu Giao Hàng",
        heading="3. Chuyển trạng thái đơn hàng",
        content="Tự động tạo phiếu giao hàng khi chuyển trạng thái",
        tokens=["Enhance", "Đồng", "bộ", "Đơn", "Hàng", "Bán", "Phiếu", "Giao"],
        title_boost=40.0,
    )
    assert matched >= 5
    assert score >= 60

    weak, weak_m = score_keyword_match(
        title="Import Kho sản phẩm lẻ",
        heading="Mô tả",
        content="Cập nhật kho",
        tokens=["Enhance", "Đồng", "bộ", "Đơn", "Hàng", "Bán", "Phiếu", "Giao"],
    )
    assert score > weak
    assert matched > weak_m


def test_strong_title_requires_literal_phrase_not_token_overlap() -> None:
    tokens = ["Đồng", "bộ", "trạng", "thái", "đơn", "bán", "hàng", "giao"]
    term = "Mô tả tóm tắt Đồng bộ trạng thái đơn bán hàng với đơn giao hàng"
    # High token overlap + high score must NOT pin SAP-style titles (no delivery note).
    assert not is_strong_title_hit(
        "Đồng bộ đơn hàng bán từ SAP (Hóa đơn trạng thái NEW)",
        term=term,
        tokens=tokens,
        score=96.0,
    )
    # Explicit page reference should pin.
    assert is_strong_title_hit(
        "[Enhance] Đồng bộ Đơn Hàng Bán với Phiếu Giao Hàng",
        term="Có trong page này [Enhance] Đồng bộ Đơn Hàng Bán với Phiếu Giao Hàng",
        tokens=["Enhance", "Đồng", "bộ", "Đơn", "Hàng", "Bán", "Phiếu", "Giao"],
        score=110.0,
    )


def test_strong_title_pins_sales_delivery_domain_without_literal_phrase() -> None:
    tokens = ["mapping", "trạng", "bảng", "thái", "đơn", "bán", "hàng", "giao"]
    term = "Cho tôi bảng mapping trạng thái giữa đơn bán hàng và đơn giao hàng"
    assert is_strong_title_hit(
        "[Enhance] Đồng bộ Đơn Hàng Bán với Phiếu Giao Hàng",
        term=term,
        tokens=tokens,
        score=80.0,
    )
    # "Giao diện" must not count as delivery intent.
    assert not is_strong_title_hit(
        "Giao diện quản lý đơn hàng bán/đơn hàng mua Thọ Phát",
        term=term,
        tokens=tokens,
        score=136.0,
    )
    # APP operational "đơn giao hàng" without phiếu giao must not pin.
    assert not is_strong_title_hit(
        "[APP] Bắt đầu giao hàng - Đơn giao hàng có nhiều đơn bán hàng (Đơn gộp)",
        term=term,
        tokens=tokens,
        score=190.0,
    )
