from __future__ import annotations

import types
from pathlib import Path

from voice_reader.infrastructure.books.parser import BookParser


def test_parser_pdf_uses_fitz_stub(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF")

    class FakePage:
        def get_text(self, mode: str) -> str:
            assert mode == "text"
            return "Hello PDF"

    class FakeDoc(list):
        pass

    fake_fitz = types.SimpleNamespace(open=lambda _: FakeDoc([FakePage(), FakePage()]))
    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)
    raw, norm = BookParser().parse(p)
    assert "Hello PDF" in raw
    assert "Hello PDF" in norm


def test_parser_epub_uses_ebooklib_bs4_stubs(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "a.epub"
    p.write_bytes(b"EPUB")

    class FakeItem:
        def get_body_content(self) -> bytes:
            return b"<html><body><h1>Title</h1><p>Text</p></body></html>"

    class FakeEpubBook:
        def get_items_of_type(self, t: int):
            assert t == 9
            return [FakeItem()]

    fake_epub = types.SimpleNamespace(read_epub=lambda _: FakeEpubBook())
    fake_ebooklib = types.SimpleNamespace(epub=fake_epub)

    class FakeSoup:
        def __init__(self, html: bytes, parser: str) -> None:
            assert parser == "html.parser"
            self._html = html

        def get_text(self, sep: str, strip: bool):
            assert sep == "\n"
            assert strip
            return "Title Text"

    fake_bs4 = types.SimpleNamespace(BeautifulSoup=FakeSoup)

    monkeypatch.setitem(__import__("sys").modules, "ebooklib", fake_ebooklib)
    monkeypatch.setitem(__import__("sys").modules, "bs4", fake_bs4)

    raw, norm = BookParser().parse(p)
    assert raw == "Title Text"
    assert norm == "Title Text"
