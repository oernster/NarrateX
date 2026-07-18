"""Cover the parser's failure and fallback paths.

Real-world EPUBs are inconsistent, so the parser carries a ladder of fallbacks:
spine first, then the manifest, then a scan by file extension, and for the text
itself BeautifulSoup, then lxml, then a crude tag strip. Each rung only runs
when the one above it fails, so each needs driving deliberately.

The stand-ins here are hand-written fakes injected as modules, matching the
style of `test_parser_epub_pdf_via_stubs`. No mocking library is involved.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.infrastructure.books.parser import BookParser, _html_to_text
from voice_reader.shared.errors import BookParseError

_ITEM_DOCUMENT = 9


def _epub_at(tmp_path: Path, name: str = "book.epub") -> Path:
    path = tmp_path / name
    path.write_bytes(b"EPUB")
    return path


def _install_ebooklib(monkeypatch, book) -> None:
    def read_epub(_path: str, options=None):
        del options
        return book

    monkeypatch.setitem(
        sys.modules,
        "ebooklib",
        types.SimpleNamespace(
            epub=types.SimpleNamespace(read_epub=read_epub),
            ITEM_DOCUMENT=_ITEM_DOCUMENT,
        ),
    )


class Doc:
    """A document item that reports its content the usual way."""

    def __init__(self, html: bytes, *, file_name: str = "c.xhtml") -> None:
        self._html = html
        self.file_name = file_name

    def get_content(self) -> bytes:
        return self._html

    def get_type(self) -> int:
        return _ITEM_DOCUMENT


def test_pdf_failure_becomes_a_book_parse_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF")

    def explode(_path: str):
        raise RuntimeError("not a PDF after all")

    monkeypatch.setitem(sys.modules, "fitz", types.SimpleNamespace(open=explode))

    with pytest.raises(BookParseError):
        BookParser().parse(path)


def test_epub_failure_becomes_a_book_parse_error(monkeypatch, tmp_path: Path) -> None:
    def always_fails(_path: str, options=None):
        del options
        raise RuntimeError("unreadable archive")

    monkeypatch.setitem(
        sys.modules,
        "ebooklib",
        types.SimpleNamespace(
            epub=types.SimpleNamespace(read_epub=always_fails),
            ITEM_DOCUMENT=_ITEM_DOCUMENT,
        ),
    )

    with pytest.raises(BookParseError):
        BookParser().parse(_epub_at(tmp_path))


def test_spine_entries_that_name_nothing_readable_are_skipped(
    monkeypatch, tmp_path: Path
) -> None:
    class NotADocument:
        def get_type(self) -> int:
            return _ITEM_DOCUMENT + 1

        def get_content(self) -> bytes:
            return b"<html><body><p>Image wrapper</p></body></html>"

    class UntypedItem:
        def get_type(self) -> int:
            raise RuntimeError("type unavailable")

        def get_content(self) -> bytes:
            return b"<html><body><p>Untyped</p></body></html>"

    items = {
        "bare": Doc(b"<html><body><p>Bare</p></body></html>"),
        "image": NotADocument(),
        "untyped": UntypedItem(),
        "good": Doc(b"<html><body><p>Good</p></body></html>"),
    }

    class Book:
        # A plain string entry, an entry with no id, the nav and cover entries
        # every EPUB3 carries, and an id the manifest does not resolve.
        spine = [
            "bare",
            ("", "yes"),
            ("nav", "yes"),
            ("cover", "yes"),
            ("missing", "yes"),
            ("image", "yes"),
            ("untyped", "yes"),
            ("good", "yes"),
        ]

        def get_item_with_id(self, item_id: str):
            return items.get(item_id)

    _install_ebooklib(monkeypatch, Book())

    parsed = BookParser().parse(_epub_at(tmp_path))

    assert "Bare" in parsed.normalized_text
    assert "Untyped" in parsed.normalized_text
    assert "Good" in parsed.normalized_text
    assert "Image wrapper" not in parsed.normalized_text


def test_manifest_documents_are_used_when_the_spine_yields_nothing(
    monkeypatch, tmp_path: Path
) -> None:
    class Book:
        spine: list[object] = []

        def get_items_of_type(self, item_type: int):
            assert item_type == _ITEM_DOCUMENT
            return [Doc(b"<html><body><p>From the manifest</p></body></html>")]

    _install_ebooklib(monkeypatch, Book())

    parsed = BookParser().parse(_epub_at(tmp_path))

    assert "From the manifest" in parsed.normalized_text


def test_undeclared_documents_are_found_by_file_extension(
    monkeypatch, tmp_path: Path
) -> None:
    class Named:
        """An item that reports its name through `get_name` rather than an
        attribute, as some EbookLib item types do."""

        def __init__(self, name: str, html: bytes) -> None:
            self._name = name
            self._html = html

        def get_name(self) -> str:
            return self._name

        def get_content(self) -> bytes:
            return self._html

    class Book:
        spine: list[object] = []

        def get_items_of_type(self, item_type: int):
            del item_type
            return []

        def get_items(self):
            return [
                Named("styles.css", b"body { color: red }"),
                Named("", b"<p>Nameless</p>"),
                Named("chapter.HTM", b"<html><body><p>Undeclared</p></body></html>"),
            ]

    _install_ebooklib(monkeypatch, Book())

    parsed = BookParser().parse(_epub_at(tmp_path))

    assert "Undeclared" in parsed.normalized_text
    assert "Nameless" not in parsed.normalized_text


def test_content_accessors_that_fail_fall_through_to_nothing(
    monkeypatch, tmp_path: Path
) -> None:
    class Silent:
        """Both content accessors raise, so the item contributes nothing."""

        def get_content(self):
            raise RuntimeError("content unavailable")

        def get_body_content(self):
            raise RuntimeError("body unavailable")

    class BodyOnly:
        def get_content(self):
            raise RuntimeError("content unavailable")

        def get_body_content(self) -> bytes:
            return b"<html><body><p>Recovered from the body</p></body></html>"

    class Empty:
        def get_content(self) -> bytes:
            return b""

        def get_body_content(self) -> bytes:
            return b""

    items = {"silent": Silent(), "body": BodyOnly(), "empty": Empty()}

    class Book:
        spine = [("silent", "yes"), ("body", "yes"), ("empty", "yes")]

        def get_item_with_id(self, item_id: str):
            return items.get(item_id)

    _install_ebooklib(monkeypatch, Book())

    parsed = BookParser().parse(_epub_at(tmp_path))

    assert parsed.normalized_text == "Recovered from the body"


def test_epub_structure_is_carried_through_as_drafts(
    monkeypatch, tmp_path: Path
) -> None:
    class Book:
        spine = [("c1", "yes")]

        def get_item_with_id(self, item_id: str):
            assert item_id == "c1"
            return Doc(b"<html><body><h2>Chapter</h2><p>Prose</p></body></html>")

    _install_ebooklib(monkeypatch, Book())

    parsed = BookParser().parse(_epub_at(tmp_path))

    assert [draft.kind for draft in parsed.drafts] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
    ]
    assert parsed.drafts[0].level == 2


def test_html_to_text_retries_with_the_builtin_parser(monkeypatch) -> None:
    class Soup:
        def __init__(self, html: bytes, parser: str) -> None:
            if parser == "lxml":
                raise RuntimeError("lxml parser unavailable")
            self._html = html

        def get_text(self, separator: str, strip: bool) -> str:
            assert (separator, strip) == ("\n", True)
            return "Built in"

    monkeypatch.setitem(
        sys.modules,
        "bs4",
        types.SimpleNamespace(BeautifulSoup=Soup, XMLParsedAsHTMLWarning=Warning),
    )

    assert _html_to_text(b"<p>ignored</p>") == "Built in"


def test_html_to_text_falls_back_to_lxml(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "bs4", None)

    text = _html_to_text(b"<html><body><p>One<br/>Two</p><p>Three</p></body></html>")

    assert "One" in text
    assert "Two" in text
    assert "Three" in text


def test_html_to_text_tolerates_elements_without_a_usable_tag(monkeypatch) -> None:
    class Element:
        """An element whose tag is not a string, as lxml reports for comments
        and processing instructions."""

        tag = object()
        tail = None

    class Document:
        def xpath(self, _expression: str):
            return [Element()]

        def text_content(self) -> str:
            return "Survived"

    monkeypatch.setitem(sys.modules, "bs4", None)
    monkeypatch.setitem(
        sys.modules,
        "lxml",
        types.SimpleNamespace(
            html=types.SimpleNamespace(fromstring=lambda _bytes: Document())
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "lxml.html",
        types.SimpleNamespace(fromstring=lambda _bytes: Document()),
    )

    assert _html_to_text(b"<!-- comment -->") == "Survived"


def test_html_to_text_strips_tags_when_no_parser_is_available(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "bs4", None)
    monkeypatch.setitem(sys.modules, "lxml", None)
    monkeypatch.setitem(sys.modules, "lxml.html", None)

    text = _html_to_text(b"<html><body><p>First</p><br/>Second</body></html>")

    assert text == "First Second"


def test_html_to_text_gives_up_on_undecodable_content(monkeypatch) -> None:
    class Undecodable:
        def decode(self, _encoding: str, errors: str) -> str:
            del errors
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "unreadable")

    monkeypatch.setitem(sys.modules, "bs4", None)
    monkeypatch.setitem(sys.modules, "lxml", None)
    monkeypatch.setitem(sys.modules, "lxml.html", None)

    assert _html_to_text(Undecodable()) == ""
