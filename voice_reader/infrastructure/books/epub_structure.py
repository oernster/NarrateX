"""Recover block structure from EPUB XHTML.

An EPUB already states its structure as `h1`..`h6`, `p`, `li`, `blockquote` and
`pre` tags. Flattening the document to text throws that away and leaves the rest
of the pipeline guessing at headings from prose. Walking the tags instead means
EPUB structure is read, not inferred.

The extracted *text* is deliberately produced exactly as before, so
`normalized_text` is unchanged and every character offset already persisted
against it keeps its meaning.
"""

from __future__ import annotations

import warnings

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind

_HEADING_LEVEL_BY_TAG = {
    "h1": 1,
    "h2": 2,
    "h3": 3,
    "h4": 4,
    "h5": 5,
    "h6": 6,
}

_KIND_BY_TAG = {
    "p": BlockKind.PARAGRAPH,
    "li": BlockKind.LIST_ITEM,
    "blockquote": BlockKind.BLOCK_QUOTE,
    "pre": BlockKind.CODE,
}

_LIST_CONTAINER_TAGS = {"ul", "ol"}

# A link out of the book is a reference; a link inside it is navigation. Only
# the second can be a contents entry.
_EXTERNAL_LINK_MARKS = ("://", "mailto:", "tel:")

_BLOCK_TAGS = sorted(set(_HEADING_LEVEL_BY_TAG) | set(_KIND_BY_TAG))

# Separator used when flattening an element to text. Matches the separator the
# EPUB text extraction has always used, so the two stay consistent.
_TEXT_SEPARATOR = " "


def _has_consumed_ancestor(element, consumed: set[int]) -> bool:
    """Whether an enclosing block element has already been emitted."""

    for parent in element.parents:
        if id(parent) in consumed:
            return True
    return False


def _list_level(element) -> int:
    """Nesting depth of a list item, counting enclosing list containers."""

    depth = 0
    for parent in element.parents:
        name = getattr(parent, "name", None)
        if name and str(name).lower() in _LIST_CONTAINER_TAGS:
            depth += 1
    return max(1, depth)


def _is_contents_entry(element, *, text: str) -> bool:
    """Whether this block is one line of a table of contents.

    The evidence is structural rather than textual: the whole block is a single
    link to somewhere else inside the book. That is what a contents entry is;
    prose is not written that way.

    It matters because a Kindle file converted to EPUB states no headings at
    all. Its contents page is a run of ordinary paragraphs, so without this the
    contents reads as body text: the pane shows a list of chapter names and the
    narrator reads them out one after another before reaching chapter one.
    """

    links = element.find_all("a")
    if len(links) != 1:
        return False
    href = str(links[0].get("href") or "").strip()
    if not href or any(mark in href.lower() for mark in _EXTERNAL_LINK_MARKS):
        return False
    return links[0].get_text(_TEXT_SEPARATOR, strip=True) == text


def _draft_for(element, *, text: str) -> BlockDraft:
    tag = str(element.name).lower()

    level = _HEADING_LEVEL_BY_TAG.get(tag)
    if level is not None:
        return BlockDraft(kind=BlockKind.HEADING, text=text, level=level)

    kind = _KIND_BY_TAG[tag]
    if _is_contents_entry(element, text=text):
        return BlockDraft(kind=BlockKind.TOC_ENTRY, text=text)
    if kind is BlockKind.LIST_ITEM:
        return BlockDraft(kind=kind, text=text, level=_list_level(element))
    return BlockDraft(kind=kind, text=text)


def drafts_from_soup(soup) -> tuple[BlockDraft, ...]:
    """Walk a parsed document, emitting one draft per block element.

    Nested block elements are emitted once, at the outermost level. A `p` inside
    a `blockquote` belongs to the quote, so the quote is emitted and the
    paragraph is not emitted again.
    """

    drafts: list[BlockDraft] = []
    consumed: set[int] = set()

    for element in soup.find_all(_BLOCK_TAGS):
        if _has_consumed_ancestor(element, consumed):
            continue
        consumed.add(id(element))

        text = element.get_text(_TEXT_SEPARATOR, strip=True)
        if not text:
            continue

        drafts.append(_draft_for(element, text=text))

    return tuple(drafts)


def parse_html(html_bytes: bytes) -> tuple[str, tuple[BlockDraft, ...]] | None:
    """Return `(text, drafts)` for one EPUB document; None if unavailable.

    Returning None means BeautifulSoup could not be used at all, so the caller
    should fall back to its own text-only extraction. The text returned here is
    byte-identical to what the previous flattening produced.
    """

    try:
        from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

        # Many EPUB documents are XHTML, which makes BeautifulSoup warn when it
        # is handed to an HTML parser. Expected here; noisy in user logs.
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

        try:
            soup = BeautifulSoup(html_bytes, "lxml")
        except Exception:
            soup = BeautifulSoup(html_bytes, "html.parser")

        text = (soup.get_text("\n", strip=True) or "").strip()
        return text, drafts_from_soup(soup)
    except Exception:
        return None
