from app.ingestion.normalize import (
    chunk_text,
    html_to_text,
    is_drawio_filename,
    replace_confluence_images,
    replace_drawio_macros_with_images,
    rewrite_attachment_urls,
    sanitize_html,
)


def test_sanitize_strips_script() -> None:
    html = '<p>Hi</p><script>alert(1)</script><img src="x" onerror="alert(1)">'
    out = sanitize_html(html)
    assert "script" not in out.lower()
    assert "onerror" not in out.lower()
    assert "Hi" in out


def test_rewrite_attachment_urls() -> None:
    html = '<img src="/download/attachments/123/diagram.png">'
    out = rewrite_attachment_urls(
        html, filename_to_attachment_id={"diagram.png": "att-1"}
    )
    assert "/api/v1/attachments/att-1/content" in out


def test_replace_confluence_images() -> None:
    html = (
        '<p><ac:image ac:height="250">'
        '<ri:attachment ri:filename="image2023-8-8_13-45-16.png"></ri:attachment>'
        "</ac:image></p>"
        "<p><strong>Hình 1</strong></p>"
    )
    out = replace_confluence_images(
        html,
        filename_to_attachment_id={"image2023-8-8_13-45-16.png": "img-att-1"},
    )
    assert "ac:image" not in out
    assert "ri:attachment" not in out
    assert 'src="/api/v1/attachments/img-att-1/content"' in out
    assert "Hình 1" in out


def test_replace_drawio_macro_with_png() -> None:
    html = (
        '<p><ac:structured-macro ac:name="drawio" ac:schema-version="1">'
        '<ac:parameter ac:name="border">true</ac:parameter>'
        '<ac:parameter ac:name="diagramName">Onboard SSC ID</ac:parameter>'
        '<ac:parameter ac:name="aspect">BzmA7BKbnzZkxEywwTMR</ac:parameter>'
        '<ac:parameter ac:name="simpleViewer">false</ac:parameter>'
        "</ac:structured-macro></p>"
    )
    out = replace_drawio_macros_with_images(
        html,
        filename_to_attachment_id={"Onboard SSC ID.png": "png-att-1"},
    )
    assert 'ac:name="drawio"' not in out
    assert "trueOnboard" not in out
    assert 'src="/api/v1/attachments/png-att-1/content"' in out
    assert 'alt="Onboard SSC ID"' in out


def test_replace_drawio_macro_missing_png() -> None:
    html = (
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">Missing Diagram</ac:parameter>'
        "</ac:structured-macro>"
    )
    out = replace_drawio_macros_with_images(html, filename_to_attachment_id={})
    assert "structured-macro" not in out
    assert "Missing Diagram" in out
    assert "preview unavailable" in out.lower()


def test_is_drawio_filename() -> None:
    assert is_drawio_filename("flow.drawio")
    assert is_drawio_filename("arch.drawio.xml")
    assert is_drawio_filename("x.dio")
    assert is_drawio_filename("foo.xml", "application/vnd.jgraph.mxfile")
    assert not is_drawio_filename("notes.pdf")


def test_chunk_html_by_headings_splits_on_h2() -> None:
    from app.ingestion.normalize import chunk_html_by_headings

    html = """
    <h1>Overview</h1><p>Intro paragraph about the project.</p>
    <h2>Payments</h2><p>Users pay tuition online after onboarding.</p>
    <h2>Support</h2><p>Contact the helpdesk for account issues.</p>
    """
    chunks = chunk_html_by_headings(html, page_title="Student Guide")
    assert len(chunks) >= 2
    headings = {c.section_heading for c in chunks}
    assert "Payments" in headings
    assert any("tuition" in c.content.lower() for c in chunks)


def test_chunk_html_keeps_table_intact() -> None:
    from app.ingestion.normalize import chunk_html_by_headings

    html = """
    <h2>Fees</h2>
    <table><tr><th>Item</th><th>Amount</th></tr><tr><td>Tuition</td><td>100</td></tr></table>
    """
    chunks = chunk_html_by_headings(html, page_title="Fees")
    assert len(chunks) == 1
    assert "| Item | Amount |" in chunks[0].content
    assert "| Tuition | 100 |" in chunks[0].content


def test_build_embed_prefix() -> None:
    from app.ingestion.normalize import build_embed_prefix, build_embed_text

    prefix = build_embed_prefix(page_title="Page A", section_heading="Section B", space_key="ENG")
    assert "Page: Page A" in prefix
    assert "Section: Section B" in prefix
    assert "Space: ENG" in prefix
    embed = build_embed_text(
        page_title="Page A",
        section_heading="Section B",
        space_key="ENG",
        content="Body text",
    )
    assert embed.endswith("Body text")


def test_chunk_text_splits() -> None:
    text = ("word " * 400).strip()
    chunks = chunk_text(text, max_chars=200, overlap=20)
    assert len(chunks) > 1
    assert all(chunks)


def test_html_to_text() -> None:
    assert "Hello" in html_to_text("<p>Hello <b>World</b></p>")
