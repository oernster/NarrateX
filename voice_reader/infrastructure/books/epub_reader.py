"""Reading an EPUB through EbookLib, whatever prefix its nav document uses.

EbookLib 0.20 finds the table of contents by parsing the nav document with an
HTML parser and asking for `//nav`. A nav written with a namespace prefix on
its XHTML elements (`<html:nav>`, as Python's ElementTree serialises one) is
valid XHTML, yet the HTML parser keeps the prefix in the tag name, so `//nav`
matches nothing and the read fails with an IndexError. The reader here hands
EbookLib the same document with those elements in the default namespace.
"""

from __future__ import annotations

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


def unprefixed_xhtml(data: bytes) -> bytes:
    """The document with any prefixed XHTML element in the default namespace.

    Answers `data` itself, byte for byte, when no XHTML element carries a
    prefix or the document is not well-formed XML; EbookLib then reads it as
    it always has. Attributes are left alone: EbookLib matches `toc` against
    any attribute, so `ns1:type="toc"` still names the table of contents.
    """

    from lxml import etree

    try:
        root = etree.fromstring(data)
    except (etree.XMLSyntaxError, ValueError):
        return data
    prefixed = [
        element
        for element in root.iter()
        if isinstance(element.tag, str)
        and element.prefix is not None
        and etree.QName(element).namespace == XHTML_NAMESPACE
    ]
    if not prefixed:
        return data
    for element in root.iter():
        if (
            isinstance(element.tag, str)
            and etree.QName(element).namespace == XHTML_NAMESPACE
        ):
            element.tag = etree.QName(element).localname
    etree.cleanup_namespaces(root)
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)


def read_epub(path: str, *, ignore_ncx: bool) -> object:
    """Read the book at `path` as `ebooklib.epub.read_epub` does."""

    from ebooklib import epub

    class _Reader(epub.EpubReader):
        def _parse_nav(self, data, base_path, navtype="toc"):
            return super()._parse_nav(
                unprefixed_xhtml(data), base_path, navtype=navtype
            )

    reader = _Reader(path, {"ignore_ncx": ignore_ncx})
    book = reader.load()
    reader.process()
    return book
