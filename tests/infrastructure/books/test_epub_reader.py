"""Tests for reading an EPUB whatever prefix its nav uses (`epub_reader`).

Built against the real EbookLib, since the defect lives in how it parses the
nav document. The books carry no NCX, so EbookLib's own fallback to the NCX
cannot rescue a nav it fails to read: only the reader can.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from voice_reader.infrastructure.books import epub_reader

_CONTAINER = (
    '<?xml version="1.0"?><container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="EPUB/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles></container>'
)
_OPF = (
    '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
    'version="3.0" unique-identifier="id"><metadata '
    'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">x'
    "</dc:identifier><dc:title>T</dc:title><dc:language>en</dc:language>"
    '</metadata><manifest><item id="nav" href="nav.xhtml" '
    'media-type="application/xhtml+xml" properties="nav"/>'
    '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
    '</manifest><spine><itemref idref="c1"/></spine></package>'
)
_CHAPTER = (
    '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>c</title></head>'
    "<body><h1>One</h1><p>Text.</p></body></html>"
)
# As pandoc output looks once ElementTree has rewritten it.
PREFIXED_NAV = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<html:html xmlns:html="http://www.w3.org/1999/xhtml" '
    'xmlns:ns1="http://www.idpf.org/2007/ops"><html:head><html:title>T'
    '</html:title></html:head><html:body><html:nav ns1:type="toc">'
    '<html:ol><html:li><html:a href="c1.xhtml">Chapter One</html:a></html:li>'
    "</html:ol></html:nav></html:body></html:html>"
)
PLAIN_NAV = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<html xmlns="http://www.w3.org/1999/xhtml" '
    'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>T</title></head>'
    '<body><nav epub:type="toc"><ol><li><a href="c1.xhtml">Chapter One</a>'
    "</li></ol></nav></body></html>"
)


def _book(tmp_path: Path, nav: str) -> Path:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _CONTAINER)
        archive.writestr("EPUB/content.opf", _OPF)
        archive.writestr("EPUB/nav.xhtml", nav)
        archive.writestr("EPUB/c1.xhtml", _CHAPTER)
    return path


@pytest.mark.parametrize("nav", [PREFIXED_NAV, PLAIN_NAV], ids=["prefixed", "plain"])
def test_the_contents_are_read_whatever_prefix_the_nav_uses(
    tmp_path: Path, nav: str
) -> None:
    book = epub_reader.read_epub(str(_book(tmp_path, nav)), ignore_ncx=True)

    assert [entry.title for entry in book.toc] == ["Chapter One"]


def test_ebooklib_alone_cannot_read_the_prefixed_nav(tmp_path: Path) -> None:
    # The defect the reader exists for; if EbookLib ever fixes it, this test
    # says the reader can go.
    from ebooklib import epub

    with pytest.raises(IndexError):
        epub.read_epub(str(_book(tmp_path, PREFIXED_NAV)), {"ignore_ncx": True})


def test_a_nav_without_a_prefix_passes_through_untouched() -> None:
    data = PLAIN_NAV.encode("utf-8")

    assert epub_reader.unprefixed_xhtml(data) is data


def test_a_nav_that_is_not_xml_passes_through_untouched() -> None:
    data = b"<html><body><nav epub:type='toc'><ol><li>unclosed</body>"

    assert epub_reader.unprefixed_xhtml(data) is data


def test_a_prefixed_nav_keeps_its_attributes_and_text() -> None:
    out = epub_reader.unprefixed_xhtml(PREFIXED_NAV.encode("utf-8"))

    assert b"<nav " in out
    assert b'ns1:type="toc"' in out
    assert b"Chapter One" in out
    assert b"html:" not in out
