from app.ingestion.storage import safe_object_filename


def test_safe_object_filename_strips_invalid_and_shortens() -> None:
    name = safe_object_filename('ChatGPT Image Aug 7, 2026, 01_38_04 PM.png')
    assert name.endswith(".png")
    assert ":" not in name
    assert len(name) < 80


def test_safe_object_filename_handles_empty() -> None:
    assert safe_object_filename("") == "file"
    assert safe_object_filename("a/b\\c?.txt").endswith(".txt")
