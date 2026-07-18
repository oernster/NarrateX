"""Classify PDF text lines into blocks using layout evidence.

A PDF states no structure, but it does carry evidence a flattened text dump
throws away: font size, weight, position on the page, and which lines the
extractor grouped together. Headings are set larger, folios sit in the margins,
running heads repeat in the same band on page after page.

This module is pure. It takes already-extracted lines and decides what each one
is, so every rule here is testable without opening a PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.artefacts import is_contents_entry, is_folio
from voice_reader.domain.document.block_kind import BlockKind

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

# A heading that is nothing but its own section number: "8", "8.1", "3.1.1".
# These are set on their own line often enough that they need rejoining with
# the title that follows.
_SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?$")

# Kinds whose text wraps across lines, so consecutive lines the extractor
# grouped together belong to one block. Furniture does not wrap: a folio or a
# running head is a line in its own right.
_WRAPPING_KINDS = frozenset({BlockKind.PARAGRAPH, BlockKind.HEADING})

# A word broken across a line end: "deci-" followed by "sion". A lowercase
# continuation means a split word; an uppercase one means a real hyphenated
# compound at a line end, which is left alone.
#
# Both hyphens count. A typeset PDF breaks words on a non-breaking hyphen as
# readily as on a plain one, and the extraction folds the two together before
# healing them, so matching only the plain one leaves every paragraph broken on
# the other kind unanchorable.
_LINE_BREAK_HYPHEN = re.compile(r"([A-Za-z])[-‑]$")
_LOWERCASE_START = re.compile(r"^[a-z]")


def join_paragraph_lines(parts: tuple[str, ...]) -> str:
    """Join wrapped lines into one paragraph, healing split words.

    Mirrors the dehyphenation the text extraction already applies, so the
    resulting text matches the canonical text and can be anchored to it.
    """

    joined = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if not joined:
            joined = piece
            continue
        if _LINE_BREAK_HYPHEN.search(joined) and _LOWERCASE_START.match(piece):
            joined = joined[:-1] + piece
            continue
        joined = f"{joined} {piece}"
    return joined


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


def drafts_from_lines(lines: tuple[PdfLine, ...]) -> tuple[BlockDraft, ...]:
    """Classify lines and merge consecutive body lines into paragraphs."""

    populated = tuple(line for line in lines if line.text.strip())
    if not populated:
        return ()

    body = body_size(populated)
    running = running_head_keys(populated)
    indexed = index_pages(populated, body=body)

    classified = _reclassify_contents_folios(
        [
            (line, _kind_of(line, body=body, running=running, indexed=indexed))
            for line in populated
        ]
    )
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
        drafts.append(BlockDraft(kind=kind, text=text, level=level))

    flush()
    return _rejoin_split_numbering(tuple(drafts))


def _rejoin_split_numbering(drafts: tuple[BlockDraft, ...]) -> tuple[BlockDraft, ...]:
    """Rejoin a heading whose number was typeset on its own line.

    Typesetting often sets "8.1" and "From possibility to constraint" as
    separate lines, so they arrive as two headings. Left apart, the number
    becomes a navigation entry of its own that says nothing, and the title
    loses the number that identifies it.

    Rejoining is safe against the canonical text because matching ignores
    whitespace: "8.1 From possibility to constraint" and the source's
    "8.1\\nFrom possibility to constraint" reduce to the same thing.
    """

    rejoined: list[BlockDraft] = []
    pending: BlockDraft | None = None

    for draft in drafts:
        is_heading = draft.kind is BlockKind.HEADING

        if is_heading and _SECTION_NUMBER.match(draft.text):
            # Two numbers in a row means the first had no title to join.
            if pending is not None:
                rejoined.append(pending)
            pending = draft
            continue

        if pending is not None:
            if is_heading:
                rejoined.append(
                    BlockDraft(
                        kind=BlockKind.HEADING,
                        text=f"{pending.text} {draft.text}",
                        level=min(pending.level, draft.level),
                    )
                )
                pending = None
                continue
            rejoined.append(pending)
            pending = None

        rejoined.append(draft)

    if pending is not None:
        rejoined.append(pending)

    return tuple(rejoined)
