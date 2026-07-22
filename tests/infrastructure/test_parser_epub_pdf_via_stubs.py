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
    parsed = BookParser().parse(p)
    raw, norm = parsed.raw_text, parsed.normalized_text
    assert "Hello PDF" in raw
    assert "Hello PDF" in norm


def test_parser_pdf_strips_running_heads_and_margin_folios(
    monkeypatch, tmp_path: Path
) -> None:
    p = tmp_path / "furnished.pdf"
    p.write_bytes(b"%PDF")

    page_height = 100.0

    def _span(text: str) -> dict:
        return {"text": text, "size": 10.0, "flags": 0}

    class FakeRect:
        height = page_height

    class FakePage:
        """A page whose dict and text modes describe the same three lines."""

        rect = FakeRect()

        def __init__(self, body: str, folio: str) -> None:
            self._body = body
            self._folio = folio

        def get_text(self, mode: str):
            if mode == "dict":
                return {
                    "blocks": [
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [_span("Contents")],
                                    "bbox": (0.0, 2.0, 0.0, 8.0),
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [_span(self._body)],
                                    "bbox": (0.0, 40.0, 0.0, 50.0),
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [_span(self._folio)],
                                    "bbox": (0.0, 92.0, 0.0, 98.0),
                                }
                            ],
                        },
                    ]
                }
            assert mode == "text"
            return f"Contents\n{self._body}\n{self._folio}"

    class FakeDoc(list):
        pass

    # Page 1's body repeats the header's exact word mid-page, proving the
    # strip is count-limited and never eats a body line.
    bodies = ["First page prose stays.", "Contents", "Third page prose stays."]
    pages = [FakePage(body, str(10 + i)) for i, body in enumerate(bodies)]
    fake_fitz = types.SimpleNamespace(open=lambda _: FakeDoc(pages))
    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)

    parsed = BookParser().parse(p)
    norm = parsed.normalized_text

    assert norm.count("Contents") == 1
    assert "First page prose stays." in norm
    assert "Third page prose stays." in norm
    for folio in ("10", "11", "12"):
        assert folio not in norm
    assert [d.text for d in parsed.drafts] == bodies


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

    parsed = BookParser().parse(p)
    raw, norm = parsed.raw_text, parsed.normalized_text
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

    parsed = BookParser().parse(p)
    raw, norm = parsed.raw_text, parsed.normalized_text
    assert "Hello" in raw
    assert "Hello" in norm
    assert calls == [{"ignore_ncx": True}, {"ignore_ncx": False}]
