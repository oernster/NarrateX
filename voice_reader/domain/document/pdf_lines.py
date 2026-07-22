"""Classify PDF text lines into blocks using layout evidence.

A PDF states no structure, but it does carry evidence a flattened text dump
throws away: font size, weight, position on the page, and which lines the
extractor grouped together. Headings are set larger, folios sit in the margins,
running heads repeat in the same band on page after page.

The furniture verdicts serve two consumers that must agree. The drafts a
caller anchors onto the canonical text omit running heads and margin folios,
because `furniture_texts_by_page` tells the text extraction to strip those
same lines from the canonical text itself. One classification pass produces
both answers, so a line can never be stripped from the text yet still be
sought by a draft, or kept in the text with no draft aware of it.

This module is pure. It takes already-extracted lines and decides what each one
is, so every rule here is testable without opening a PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.artefacts import is_contents_entry, is_folio
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.pdf_line_assembly import (
    join_paragraph_lines,
    rejoin_split_numbering,
)

# A heading is set noticeably larger than body text. Below this the difference
# is more likely to be extraction noise than an editorial decision.
_HEADING_SIZE_RATIO = 1.15

# Headings are short. A long run of larger text is more likely a pull quote or
# a mis-measured paragraph than a heading.
_MAX_HEADING_WORDS = 20

# Deepest heading level the model expresses, matching HTML's h1 to h6.
_MAX_HEADING_LEVEL = 6

# Fraction of page height at the top and bottom treated as margin furniture.
_EDGE_BAND_RATIO = 0.12

# How many distinct pages a margin line must recur on to count as a running
# head or foot. Three separates a genuine repeat from a coincidence.
_RUNNING_REPEAT_MIN_PAGES = 3

# Running heads that name a page as part of the book's index. A page announcing
# itself this way is far better evidence than the shape of its lines: an index
# entry ("latency, 60, 189") and a wrapped body line ending in a year read
# almost identically, and only one of them sits under this heading.
_INDEX_HEAD_KEYS = frozenset({"index", "subject index", "name index"})

_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")

# Kinds whose text wraps across lines, so consecutive lines the extractor
# grouped together belong to one block. Furniture does not wrap: a folio or a
# running head is a line in its own right.
_WRAPPING_KINDS = frozenset({BlockKind.PARAGRAPH, BlockKind.HEADING})


@dataclass(frozen=True, slots=True)
class PdfLine:
    """One extracted line, with the layout evidence needed to classify it."""

    text: str
    size: float
    bold: bool
    top: float
    bottom: float
    page_index: int
    page_height: float
    # Index of the extractor's own grouping on the page. Lines sharing one are
    # a paragraph as far as the extractor could tell.
    block_index: int

    @property
    def key(self) -> tuple[int, int]:
        return self.page_index, self.block_index


def _repetition_key(text: str) -> str:
    """Normalise a margin line so it matches its twin on other pages.

    Digits are dropped because the page number is the part that changes:
    "Chapter 3 | 45" and "Chapter 3 | 46" are the same running head.
    """

    stripped = _DIGITS.sub("", str(text or "")).strip().casefold()
    return _WHITESPACE.sub(" ", stripped)


def _in_edge_band(line: PdfLine) -> bool:
    if line.page_height <= 0:
        return False
    band = line.page_height * _EDGE_BAND_RATIO
    return line.top <= band or line.bottom >= line.page_height - band


def body_size(lines: tuple[PdfLine, ...]) -> float:
    """The dominant body font size, weighted by how much text is set in it."""

    weights: dict[float, int] = {}
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        key = round(line.size, 1)
        weights[key] = weights.get(key, 0) + len(text)

    if not weights:
        return 0.0
    return max(weights.items(), key=lambda item: (item[1], item[0]))[0]


def running_head_keys(lines: tuple[PdfLine, ...]) -> frozenset[str]:
    """Repetition keys of lines that recur in the margins across pages."""

    pages_by_key: dict[str, set[int]] = {}
    for line in lines:
        if not _in_edge_band(line):
            continue
        key = _repetition_key(line.text)
        if not key:
            continue
        pages_by_key.setdefault(key, set()).add(line.page_index)

    return frozenset(
        key
        for key, pages in pages_by_key.items()
        if len(pages) >= _RUNNING_REPEAT_MIN_PAGES
    )


def index_pages(lines: tuple[PdfLine, ...], *, body: float) -> frozenset[int]:
    """Pages that name themselves as part of the book's index.

    Two signals, because typesetting uses both. Later pages carry "Index" as a
    running head in the margin, while the opening page of the index carries it
    as a title instead and usually suppresses the running head, which is why
    the margin alone always misses the first page.

    Repetition is not required, unlike an ordinary running head. A generic line
    needs to recur before it reads as furniture, whereas a line that says
    "Index" has already said what the page is. Requiring a repeat would also
    miss every two-page index, which is most of them.
    """

    return frozenset(
        line.page_index
        for line in lines
        if _repetition_key(line.text) in _INDEX_HEAD_KEYS
        and (_in_edge_band(line) or _looks_like_heading(line, body=body))
    )


def _looks_like_heading(line: PdfLine, *, body: float) -> bool:
    text = line.text.strip()
    if not text or len(text.split()) > _MAX_HEADING_WORDS:
        return False
    if body <= 0:
        return False
    if line.size >= body * _HEADING_SIZE_RATIO:
        return True
    # Same size but bold and short still reads as a heading in many books.
    return line.bold and line.size >= body


def _heading_levels(sizes: set[float]) -> dict[float, int]:
    """Rank distinct heading sizes, largest first, into levels from one."""

    ordered = sorted(sizes, reverse=True)
    return {
        size: min(index + 1, _MAX_HEADING_LEVEL) for index, size in enumerate(ordered)
    }


def _kind_of(
    line: PdfLine,
    *,
    body: float,
    running: frozenset[str],
    indexed: frozenset[int],
) -> BlockKind:
    text = line.text.strip()
    if is_contents_entry(text):
        return BlockKind.TOC_ENTRY
    if is_folio(text) and _in_edge_band(line):
        return BlockKind.PAGE_NUMBER
    if _in_edge_band(line) and _repetition_key(text) in running:
        return BlockKind.RUNNING_HEAD
    if _looks_like_heading(line, body=body):
        return BlockKind.HEADING
    if line.page_index in indexed:
        return BlockKind.INDEX_ENTRY
    return BlockKind.PARAGRAPH


def _reclassify_contents_folios(
    classified: list[tuple[PdfLine, BlockKind]],
) -> list[tuple[PdfLine, BlockKind]]:
    """Reclaim page numbers that belong to a contents list.

    A two-column contents page extracts as alternating titles and page numbers,
    so the numbers land in the middle of the page rather than the margin and
    would otherwise be read as prose. A bare number touching a contents entry
    belongs to that entry.
    """

    kinds = [kind for _, kind in classified]

    for index, (line, kind) in enumerate(classified):
        if kind is not BlockKind.PARAGRAPH or not is_folio(line.text):
            continue
        neighbours = kinds[max(0, index - 1) : index] + kinds[index + 1 : index + 2]
        if BlockKind.TOC_ENTRY in neighbours:
            classified[index] = (line, BlockKind.PAGE_NUMBER)

    return classified


def _classify(lines: tuple[PdfLine, ...]) -> list[tuple[PdfLine, BlockKind]]:
    """One classification pass shared by drafts and furniture selection."""

    body = body_size(lines)
    running = running_head_keys(lines)
    indexed = index_pages(lines, body=body)

    return _reclassify_contents_folios(
        [
            (line, _kind_of(line, body=body, running=running, indexed=indexed))
            for line in lines
        ]
    )


def _is_stripped_furniture(line: PdfLine, kind: BlockKind) -> bool:
    """Whether this line is removed from the canonical text entirely.

    Running heads always are. A folio is only stripped when it sits in the
    margin band; a reclassified contents-column number sits mid-page, stays in
    the text and therefore keeps its draft.
    """

    if kind is BlockKind.RUNNING_HEAD:
        return True
    return kind is BlockKind.PAGE_NUMBER and _in_edge_band(line)


def furniture_texts_by_page(
    lines: tuple[PdfLine, ...],
) -> dict[int, tuple[str, ...]]:
    """Texts of the furniture lines to strip from each page's extracted text.

    Keyed by page index. The counts matter: a page contributes one entry per
    furniture line, so the caller can consume at most that many matching lines
    and leave body text that happens to repeat the header's words alone.
    """

    populated = tuple(line for line in lines if line.text.strip())
    if not populated:
        return {}

    texts: dict[int, list[str]] = {}
    for line, kind in _classify(populated):
        if _is_stripped_furniture(line, kind):
            texts.setdefault(line.page_index, []).append(line.text.strip())

    return {page: tuple(entries) for page, entries in texts.items()}


def drafts_from_lines(lines: tuple[PdfLine, ...]) -> tuple[BlockDraft, ...]:
    """Classify lines and merge consecutive body lines into paragraphs.

    Stripped furniture (running heads, margin folios) yields no draft: its
    text is removed from the canonical source, so a draft for it could only
    fail to anchor, or worse, anchor onto an innocent body occurrence of the
    same words and steal the paragraph that owns them. It still breaks up the
    surrounding blocks exactly as it did on the page.
    """

    populated = tuple(line for line in lines if line.text.strip())
    if not populated:
        return ()

    classified = _classify(populated)
    levels = _heading_levels(
        {round(line.size, 1) for line, kind in classified if kind is BlockKind.HEADING}
    )

    drafts: list[BlockDraft] = []
    pending: list[str] = []
    pending_key: tuple[int, int] | None = None
    pending_kind = BlockKind.PARAGRAPH
    pending_level = 0

    def flush() -> None:
        if not pending:
            return
        text = join_paragraph_lines(tuple(pending)).strip()
        pending.clear()
        if text:
            drafts.append(BlockDraft(kind=pending_kind, text=text, level=pending_level))

    for line, kind in classified:
        text = line.text.strip()
        level = levels.get(round(line.size, 1), 1) if kind is BlockKind.HEADING else 0

        # A heading wraps like a paragraph does. "Chapter 1: Decision objects
        # and the" / "shape of organisational systems" is one title, and taking
        # a line at a time leaves the second half starting mid-sentence, or
        # mid-word where the break was hyphenated.
        if kind in _WRAPPING_KINDS:
            # A new grouping from the extractor starts a new block, and so does
            # a change of kind or of heading rank.
            same_run = (
                pending_key == line.key
                and pending_kind is kind
                and pending_level == level
            )
            if pending and not same_run:
                flush()
            pending.append(text)
            pending_key = line.key
            pending_kind = kind
            pending_level = level
            continue

        flush()
        pending_key = None
        if _is_stripped_furniture(line, kind):
            continue
        drafts.append(BlockDraft(kind=kind, text=text, level=level))

    flush()
    return rejoin_split_numbering(tuple(drafts))
