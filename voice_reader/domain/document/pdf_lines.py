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

_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")

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

    classified = _reclassify_contents_folios(
        [(line, _kind_of(line, body=body, running=running)) for line in populated]
    )
    levels = _heading_levels(
        {round(line.size, 1) for line, kind in classified if kind is BlockKind.HEADING}
    )

    drafts: list[BlockDraft] = []
    pending: list[str] = []
    pending_key: tuple[int, int] | None = None

    def flush() -> None:
        if not pending:
            return
        text = join_paragraph_lines(tuple(pending)).strip()
        pending.clear()
        if text:
            drafts.append(BlockDraft(kind=BlockKind.PARAGRAPH, text=text))

    for line, kind in classified:
        text = line.text.strip()

        if kind is BlockKind.PARAGRAPH:
            # A new grouping from the extractor starts a new paragraph.
            if pending_key is not None and line.key != pending_key:
                flush()
            pending.append(text)
            pending_key = line.key
            continue

        flush()
        pending_key = None

        level = levels.get(round(line.size, 1), 1) if kind is BlockKind.HEADING else 0
        drafts.append(BlockDraft(kind=kind, text=text, level=level))

    flush()
    return tuple(drafts)
