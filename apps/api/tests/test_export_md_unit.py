from __future__ import annotations

import zipfile
from io import BytesIO
from uuid import uuid4

from app.ingestion.export_md import (
    ExportPage,
    build_md_zip,
    html_to_markdown,
    page_markdown,
    safe_slug,
    unique_zip_name,
)


def test_safe_slug_strips_unsafe() -> None:
    assert safe_slug("Hello / World?") == "Hello_World"
    assert safe_slug("") == "page"


def test_html_to_markdown_keeps_structure_and_omits_images() -> None:
    html = """
    <h1>Title</h1>
    <p>Hello <strong>world</strong> and <a href="https://ex.com">link</a>.</p>
    <ul><li>One</li><li>Two</li></ul>
    <img src="/api/v1/attachments/1/content" alt="Diagram A" />
    <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
    """
    md = html_to_markdown(html)
    assert "# Title" in md
    assert "**world**" in md
    assert "[link](https://ex.com)" in md
    assert "- One" in md
    assert "*[Image: Diagram A]*" in md
    assert "/api/v1/attachments" not in md
    assert "| A | B |" in md


def test_page_markdown_frontmatter() -> None:
    page = ExportPage(
        id=uuid4(),
        title="Refund Policy",
        external_url="https://confluence.example/x",
        parent_id=None,
        depth=0,
        position=0,
        raw_content="<p>Within <em>30</em> days.</p>",
        normalized_content=None,
    )
    md = page_markdown(page, source_name="KB Space", path="Refund Policy")
    assert md.startswith("---\n")
    assert 'title: "Refund Policy"' in md or "title: Refund Policy" in md
    assert "source: " in md
    assert "external_url:" in md
    assert "# Refund Policy" in md
    assert "*30*" in md


def test_build_md_zip_unique_names() -> None:
    a = uuid4()
    b = uuid4()
    pages = [
        ExportPage(
            id=a,
            title="Same",
            external_url=None,
            parent_id=None,
            depth=0,
            position=0,
            raw_content="<p>A</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=b,
            title="Same",
            external_url=None,
            parent_id=a,
            depth=1,
            position=0,
            raw_content="<p>B</p>",
            normalized_content=None,
        ),
    ]
    data = build_md_zip(pages, source_name="Src")
    assert data[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = sorted(zf.namelist())
    # Depth 0 and 1 stay separate bundles when group_depth=2
    assert len(names) == 2
    assert names[0].endswith(".md")
    assert names[0] != names[1]


def test_build_md_zip_groups_at_depth_2() -> None:
    from app.ingestion.export_md import bundle_root_id

    root = uuid4()
    l1 = uuid4()
    l2a = uuid4()
    l2b = uuid4()
    child = uuid4()
    pages = [
        ExportPage(
            id=root,
            title="Root",
            external_url=None,
            parent_id=None,
            depth=0,
            position=0,
            raw_content="<p>R</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=l1,
            title="Level1",
            external_url=None,
            parent_id=root,
            depth=1,
            position=0,
            raw_content="<p>L1</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=l2a,
            title="BranchA",
            external_url=None,
            parent_id=l1,
            depth=2,
            position=0,
            raw_content="<p>A</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=child,
            title="Deep",
            external_url=None,
            parent_id=l2a,
            depth=3,
            position=0,
            raw_content="<p>Deep body</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=l2b,
            title="BranchB",
            external_url=None,
            parent_id=l1,
            depth=2,
            position=1,
            raw_content="<p>B</p>",
            normalized_content=None,
        ),
    ]
    by_id = {p.id: p for p in pages}
    assert bundle_root_id(pages[3], by_id) == l2a  # deep → BranchA
    assert bundle_root_id(pages[2], by_id) == l2a
    assert bundle_root_id(pages[1], by_id) == l1
    assert bundle_root_id(pages[0], by_id) == root

    data = build_md_zip(pages, source_name="Src")
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = sorted(zf.namelist())
        texts = {n: zf.read(n).decode("utf-8") for n in names}
    # Root, Level1, BranchA(+Deep), BranchB → 4 files
    assert len(names) == 4
    branch_a = next(t for t in texts.values() if "BranchA" in t and "pages: 2" in t)
    assert "Deep body" in branch_a
    assert "# BranchA" in branch_a
    assert "## Deep" in branch_a or "# Deep" in branch_a


def test_build_md_zip_group_depth_0_one_file_per_page() -> None:
    root = uuid4()
    child = uuid4()
    pages = [
        ExportPage(
            id=root,
            title="Root",
            external_url=None,
            parent_id=None,
            depth=0,
            position=0,
            raw_content="<p>R</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=child,
            title="Child",
            external_url=None,
            parent_id=root,
            depth=1,
            position=0,
            raw_content="<p>C</p>",
            normalized_content=None,
        ),
    ]
    data = build_md_zip(pages, source_name="Src", group_depth=0)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = sorted(zf.namelist())
        texts = [zf.read(n).decode("utf-8") for n in names]
    assert len(names) == 2
    assert all("pages:" not in t for t in texts)  # single-page frontmatter, no bundle count


def test_build_md_zip_group_depth_1_merges_deeper() -> None:
    root = uuid4()
    l1 = uuid4()
    deep = uuid4()
    pages = [
        ExportPage(
            id=root,
            title="Root",
            external_url=None,
            parent_id=None,
            depth=0,
            position=0,
            raw_content="<p>R</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=l1,
            title="Level1",
            external_url=None,
            parent_id=root,
            depth=1,
            position=0,
            raw_content="<p>L1</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=deep,
            title="Deep",
            external_url=None,
            parent_id=l1,
            depth=2,
            position=0,
            raw_content="<p>Deep body</p>",
            normalized_content=None,
        ),
    ]
    data = build_md_zip(pages, source_name="Src", group_depth=1)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = sorted(zf.namelist())
        texts = {n: zf.read(n).decode("utf-8") for n in names}
    # Root alone + Level1(+Deep) → 2 files
    assert len(names) == 2
    merged = next(t for t in texts.values() if "pages: 2" in t)
    assert "Deep body" in merged
    assert "Level1" in merged


def test_count_export_files_matches_zip() -> None:
    from app.ingestion.export_md import count_export_files, preview_export_file_counts

    root = uuid4()
    l1 = uuid4()
    deep = uuid4()
    pages = [
        ExportPage(
            id=root,
            title="Root",
            external_url=None,
            parent_id=None,
            depth=0,
            position=0,
            raw_content="<p>R</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=l1,
            title="Level1",
            external_url=None,
            parent_id=root,
            depth=1,
            position=0,
            raw_content="<p>L1</p>",
            normalized_content=None,
        ),
        ExportPage(
            id=deep,
            title="Deep",
            external_url=None,
            parent_id=l1,
            depth=2,
            position=0,
            raw_content="<p>D</p>",
            normalized_content=None,
        ),
    ]
    assert count_export_files(pages, group_depth=0) == 3
    assert count_export_files(pages, group_depth=1) == 2
    assert count_export_files(pages, group_depth=2) == 3
    preview = preview_export_file_counts(pages)
    assert preview["0"] == 3
    assert preview["1"] == 2

    for depth in (0, 1, 2):
        data = build_md_zip(pages, source_name="Src", group_depth=depth)
        with zipfile.ZipFile(BytesIO(data)) as zf:
            assert len(zf.namelist()) == count_export_files(pages, group_depth=depth)


def test_unique_zip_name_collision() -> None:
    used: set[str] = set()
    first = unique_zip_name(1, "Doc", used)
    second = unique_zip_name(1, "Doc", used)
    assert first == "0001-Doc.md"
    assert second == "0001-Doc-2.md"
