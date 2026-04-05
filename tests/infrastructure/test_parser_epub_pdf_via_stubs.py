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
        spine = [("c1", "yes")]

        def get_item_with_id(self, item_id: str):
            assert item_id == "c1"
            return FakeItem()

        def get_items_of_type(self, t: int):
            assert t == 9
            return [FakeItem()]

    def fake_read_epub(_path: str, options=None):
        # The parser may pass EbookLib options.
        del options
        return FakeEpubBook()

    fake_epub = types.SimpleNamespace(read_epub=fake_read_epub)
    fake_ebooklib = types.SimpleNamespace(epub=fake_epub, ITEM_DOCUMENT=9)

    class FakeSoup:
        def __init__(self, html: bytes, parser: str) -> None:
            assert parser in {"lxml", "html.parser"}
            self._html = html

        def get_text(self, sep: str, strip: bool):
            assert sep == "\n"
            assert strip
            # New EPUB parser logic preserves block boundaries.
            return "Title\n\nText"

    class FakeXMLParsedAsHTMLWarning(Warning):
        pass

    fake_bs4 = types.SimpleNamespace(
        BeautifulSoup=FakeSoup,
        XMLParsedAsHTMLWarning=FakeXMLParsedAsHTMLWarning,
    )

    monkeypatch.setitem(__import__("sys").modules, "ebooklib", fake_ebooklib)
    monkeypatch.setitem(__import__("sys").modules, "bs4", fake_bs4)

    raw, norm = BookParser().parse(p)
    assert raw == "Title\n\nText"
    assert norm == "Title\n\nText"


def test_parser_epub_retries_ignore_ncx_when_default_read_fails(
    monkeypatch, tmp_path: Path
) -> None:
    p = tmp_path / "b.epub"
    p.write_bytes(b"EPUB")

    class FakeItem:
        def get_content(self) -> bytes:
            return b"<html><body><p>Hello</p></body></html>"

    class FakeEpubBook:
        spine = [("c1", "yes")]

        def get_item_with_id(self, item_id: str):
            assert item_id == "c1"
            return FakeItem()

    calls: list[object] = []

    def fake_read_epub(_path: str, options=None):
        calls.append(options)
        if options == {"ignore_ncx": True}:
            raise IndexError("nav parse failed")
        return FakeEpubBook()

    fake_epub = types.SimpleNamespace(read_epub=fake_read_epub)
    fake_ebooklib = types.SimpleNamespace(epub=fake_epub, ITEM_DOCUMENT=9)

    class FakeSoup:
        def __init__(self, html: bytes, parser: str) -> None:
            self._html = html
            self._parser = parser

        def get_text(self, sep: str, strip: bool):
            assert sep == "\n"
            assert strip
            return "Hello"

    fake_bs4 = types.SimpleNamespace(BeautifulSoup=FakeSoup)

    monkeypatch.setitem(__import__("sys").modules, "ebooklib", fake_ebooklib)
    monkeypatch.setitem(__import__("sys").modules, "bs4", fake_bs4)

    raw, norm = BookParser().parse(p)
    assert "Hello" in raw
    assert "Hello" in norm
    assert calls == [{"ignore_ncx": True}, {"ignore_ncx": False}]
