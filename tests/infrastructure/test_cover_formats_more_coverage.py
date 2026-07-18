"""Cover the per-format cover strategies.

EPUB cover extraction reads a real zip, because the awkward cases are all shapes
a real EPUB takes: a relative path with a dot segment, an empty cover document,
a cover page whose only link is a stylesheet or an anchor. Kindle conversion and
PDF rasterising call out to tools that are not present in the test environment,
so those two get hand-written stand-ins.
"""

from __future__ import annotations

import subprocess
import sys
import types
import zipfile
from pathlib import Path

from voice_reader.infrastructure.books.cover.epub import extract_epub_cover
from voice_reader.infrastructure.books.cover.kindle import extract_kindle_via_conversion
from voice_reader.infrastructure.books.cover.pdf import extract_pdf_cover


def _epub(path: Path, entries: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return path


def test_a_dot_segment_in_the_href_is_normalised(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "dot.epub",
        {
            "OEBPS/cover.xhtml": '<html><img src="./images/cover.jpg"/></html>',
            "OEBPS/images/cover.jpg": b"DOTTED",
        },
    )

    assert extract_epub_cover(book) == b"DOTTED"


def test_an_empty_cover_document_is_passed_over(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "empty.epub",
        {
            "cover.xhtml": b"",
            "sub/cover.html": '<html><img src="art.png"/></html>',
            "sub/art.png": b"SECOND",
        },
    )

    assert extract_epub_cover(book) == b"SECOND"


def test_a_cover_document_with_no_links_falls_through(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "bare.epub",
        {
            "cover.xhtml": "<html><body>Cover</body></html>",
            "images/plate.png": b"HEURISTIC",
        },
    )

    assert extract_epub_cover(book) == b"HEURISTIC"


def test_a_non_image_link_is_tried_before_the_heuristic(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "styled.epub",
        {
            "cover.xhtml": '<html><link href="style.css"/></html>',
            "images/plate.png": b"HEURISTIC",
        },
    )

    assert extract_epub_cover(book) == b"HEURISTIC"


def test_an_anchor_only_link_is_skipped(tmp_path: Path) -> None:
    book = _epub(
        tmp_path / "anchor.epub",
        {
            "cover.xhtml": '<html><a href="#start">Start</a></html>',
            "images/plate.png": b"HEURISTIC",
        },
    )

    assert extract_epub_cover(book) == b"HEURISTIC"


def test_a_book_with_no_images_has_no_cover(tmp_path: Path) -> None:
    book = _epub(tmp_path / "textonly.epub", {"text/ch1.xhtml": "<html>Text</html>"})

    assert extract_epub_cover(book) is None


def test_a_failed_conversion_yields_no_kindle_cover(
    monkeypatch, tmp_path: Path
) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")

    def failed_run(cmd, capture_output: bool, text: bool, check: bool):
        del cmd, capture_output, text, check
        return types.SimpleNamespace(
            returncode=1, stdout="", stderr="conversion failed"
        )

    monkeypatch.setattr(subprocess, "run", failed_run)

    def unreachable(_path: Path):
        raise AssertionError("no EPUB was produced")

    assert extract_kindle_via_conversion(book, extract_epub_cover=unreachable) is None


def test_a_conversion_that_raises_yields_no_kindle_cover(
    monkeypatch, tmp_path: Path
) -> None:
    book = tmp_path / "Book.azw3"
    book.write_bytes(b"dummy")

    def succeeded_run(cmd, capture_output: bool, text: bool, check: bool):
        del capture_output, text, check
        Path(cmd[2]).write_bytes(b"not a real epub")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", succeeded_run)

    def explodes(_path: Path):
        raise RuntimeError("cover extraction failed")

    assert extract_kindle_via_conversion(book, extract_epub_cover=explodes) is None


def test_a_pdf_with_no_pages_has_no_cover(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF")

    class PagelessDocument:
        page_count = 0

    monkeypatch.setitem(
        sys.modules,
        "fitz",
        types.SimpleNamespace(open=lambda _path: PagelessDocument()),
    )

    assert extract_pdf_cover(pdf) is None
