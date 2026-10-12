from app.confluence.ssrf import SsrfBlocked, assert_public_url, normalize_base_url
import pytest


def test_normalize_base_url_adds_https() -> None:
    assert normalize_base_url("confluence.example.com") == "https://confluence.example.com"


def test_normalize_base_url_strips_path() -> None:
    assert (
        normalize_base_url("https://confluence.example.com/wiki/home")
        == "https://confluence.example.com"
    )


def test_ssrf_blocks_localhost() -> None:
    with pytest.raises(SsrfBlocked):
        assert_public_url("https://localhost", allow_http=False, allow_private=False)


def test_ssrf_allows_private_when_enabled() -> None:
    assert assert_public_url(
        "http://127.0.0.1", allow_http=True, allow_private=True
    ).startswith("http://")
