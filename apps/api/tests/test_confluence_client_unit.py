from app.confluence.client import ConfluenceClient, cookie_names, normalize_cookie_header


def test_normalize_cookie_bare_jsession() -> None:
    assert normalize_cookie_header("ABC123") == "JSESSIONID=ABC123"


def test_normalize_cookie_full_header() -> None:
    raw = "Cookie: JSESSIONID=abc; seraph.rememberme=xyz"
    assert normalize_cookie_header(raw) == "JSESSIONID=abc; seraph.rememberme=xyz"


def test_normalize_cookie_multiline_devtools() -> None:
    raw = "JSESSIONID=abc\nseraph.rememberme=xyz\nPath=/\n"
    assert normalize_cookie_header(raw) == "JSESSIONID=abc; seraph.rememberme=xyz"


def test_normalize_cookie_json_export() -> None:
    raw = '[{"name":"JSESSIONID","value":"abc"},{"name":"seraph.rememberme","value":"xyz"}]'
    assert normalize_cookie_header(raw) == "JSESSIONID=abc; seraph.rememberme=xyz"


def test_normalize_cookie_chrome_table() -> None:
    raw = "Name\tValue\tDomain\nJSESSIONID\tabc\tkb.example.com\nseraph.rememberme\txyz\tkb.example.com\n"
    assert normalize_cookie_header(raw) == "JSESSIONID=abc; seraph.rememberme=xyz"


def test_cookie_names() -> None:
    assert cookie_names("JSESSIONID=abc; seraph.rememberme=xyz") == [
        "JSESSIONID",
        "seraph.rememberme",
    ]


def test_normalize_ancestors_list_and_results_wrapper() -> None:
    from app.confluence.client import normalize_ancestors

    listed = normalize_ancestors(
        [{"id": "1", "title": "Home", "type": "page"}, {"id": "2", "title": "Child"}]
    )
    assert [a["id"] for a in listed] == ["1", "2"]
    wrapped = normalize_ancestors({"results": [{"id": 9, "title": "P", "type": "page"}]})
    assert listed and wrapped[0]["id"] == "9"
    assert normalize_ancestors({"results": [{"id": "s", "type": "space"}]}) == []
    assert normalize_ancestors(None) == []

def test_anonymous_user_detected() -> None:
    assert ConfluenceClient._is_anonymous_user({"type": "anonymous", "username": "Anonymous"})
    assert ConfluenceClient._is_anonymous_user({"username": "Anonymous"})
    assert not ConfluenceClient._is_anonymous_user(
        {"type": "known", "username": "jdoe", "displayName": "Jane"}
    )
