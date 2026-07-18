"""Build a document model from plain text.

Plain text states nothing. There are no tags to read and no font sizes to
measure, so this is the only format where structure is genuinely guessed. Every
rule here is therefore conservative: it would rather leave a heading looking
like a paragraph than swallow a paragraph as furniture.

Because the text is already the canonical text, spans are exact by
construction. Nothing needs anchoring and nothing can be dropped.
"""

from __future__ import annotations

import re

from voice_reader.domain.document.artefacts import is_contents_entry, is_folio
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.markdown_lines import (
    Line,
    is_blank,
    is_thematic_break,
    split_lines,
)
from voice_reader.domain.document.model import Block, Document
from voice_reader.domain.document.sectioning import build_toc, group_into_sections

# A heading is short. Longer than this and it reads as prose however it is set.
_MAX_HEADING_WORDS = 12

# How many times a short line must recur verbatim before it is treated as a
# running head. Prose rarely repeats word for word.
_MIN_REPEATS_FOR_RUNNING_HEAD = 3

# A numbered division: "Chapter 4", "Part Two", "Book III", "Appendix A".
_NUMBERED_DIVISION = re.compile(
    r"^(chapter|part|book|section|appendix|volume)\b[\s.:-]*\S",
    re.IGNORECASE,
)

# Divisions that stand alone with no number after them.
_STANDALONE_DIVISIONS = frozenset(
    {
        "contents",
        "table of contents",
        "prologue",
        "epilogue",
        "introduction",
        "foreword",
        "preface",
        "afterword",
        "acknowledgements",
        "acknowledgments",
        "appendix",
        "glossary",
        "bibliography",
        "notes",
        "index",
        "about the author",
    }
)

_SENTENCE_END = re.compile(r"[.!?:;,]$")
_HAS_LETTER = re.compile(r"[A-Za-z]")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")


def _is_short(text: str) -> bool:
    return len(text.split()) <= _MAX_HEADING_WORDS


def _is_shouted(text: str) -> bool:
    """Whether the line is set in capitals, a common plain-text heading."""

    return bool(_HAS_LETTER.search(text)) and text == text.upper()


def _division_level(text: str) -> int | None:
    """Heading level for a named division, or None if it is not one."""

    stripped = text.strip().rstrip(".").casefold()
    if stripped in _STANDALONE_DIVISIONS:
        return 1
    if _NUMBERED_DIVISION.match(text.strip()):
        return 1
    return None


def _repetition_key(text: str) -> str:
    stripped = _DIGITS.sub("", text).strip().casefold()
    return _WHITESPACE.sub(" ", stripped)


def _running_head_keys(lines: tuple[Line, ...]) -> frozenset[str]:
    """Keys of short lines that recur verbatim often enough to be furniture.

    Only isolated lines count. A repeated line that sits inside a paragraph is
    prose that happens to recur, not a running head, and swallowing it would
    delete real content. Requiring isolation is what keeps the first line of a
    repeated paragraph out of this set.
    """

    counts: dict[str, int] = {}
    for index, line in enumerate(lines):
        text = line.text.strip()
        if not text or not _is_short(text) or _SENTENCE_END.search(text):
            continue
        if not _is_isolated(lines, index):
            continue
        key = _repetition_key(text)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1

    return frozenset(
        key for key, count in counts.items() if count >= _MIN_REPEATS_FOR_RUNNING_HEAD
    )


def _heading_level(text: str, *, isolated: bool) -> int | None:
    """Heading level for a line, or None if it reads as prose.

    `isolated` means the line stands alone between blank lines, which is the
    only evidence plain text offers that a short line is a title rather than
    the first line of a paragraph.

    Named divisions are not handled here: the caller settles those first,
    because they must outrank running-head detection.
    """

    if not _is_short(text):
        return None
    if _is_shouted(text):
        return 1
    if isolated and not _SENTENCE_END.search(text):
        return 2
    return None


def _kind_of(
    text: str,
    *,
    isolated: bool,
    running: frozenset[str],
) -> tuple[BlockKind, int]:
    if is_contents_entry(text):
        return BlockKind.TOC_ENTRY, 0
    if is_folio(text):
        return BlockKind.PAGE_NUMBER, 0
    if is_thematic_break(text):
        return BlockKind.SEPARATOR, 0

    # A named division wins over repetition. The repetition key drops digits so
    # that "Chapter 3 | 45" matches its twin on the next page, which also makes
    # "Chapter 1", "Chapter 2" and "Chapter 3" collide. Without this check
    # first, a book's own chapter titles would be discarded as furniture.
    division = _division_level(text)
    if division is not None:
        return BlockKind.HEADING, division

    if _repetition_key(text) in running:
        return BlockKind.RUNNING_HEAD, 0

    level = _heading_level(text, isolated=isolated)
    if level is not None:
        return BlockKind.HEADING, level
    return BlockKind.PARAGRAPH, 0


def _is_isolated(lines: tuple[Line, ...], index: int) -> bool:
    before_blank = index == 0 or is_blank(lines[index - 1].text)
    after_blank = index + 1 >= len(lines) or is_blank(lines[index + 1].text)
    return before_blank and after_blank


def scan_blocks(*, source: str) -> tuple[Block, ...]:
    """Return plain text as an ordered run of blocks with exact spans."""

    lines = split_lines(source)
    if not lines:
        return ()

    running = _running_head_keys(lines)

    blocks: list[Block] = []
    pending: list[Line] = []

    def flush() -> None:
        if not pending:
            return
        run = list(pending)
        pending.clear()
        # Only non-blank lines are ever pending, so the join is never empty.
        text = " ".join(line.text.strip() for line in run).strip()
        blocks.append(
            Block(
                kind=BlockKind.PARAGRAPH,
                source_start=run[0].start,
                source_end=run[-1].end,
                text=text,
            )
        )

    for index, line in enumerate(lines):
        text = line.text.strip()
        if not text:
            flush()
            continue

        kind, level = _kind_of(
            text,
            isolated=_is_isolated(lines, index),
            running=running,
        )
        if kind is BlockKind.PARAGRAPH:
            pending.append(line)
            continue

        flush()
        blocks.append(
            Block(
                kind=kind,
                source_start=line.start,
                source_end=line.end,
                text=text,
                level=level,
            )
        )

    flush()
    return tuple(blocks)


def build_document(*, source: str) -> Document:
    """Build the full document model for plain text `source`."""

    body = str(source or "")
    blocks = scan_blocks(source=body)
    sections = group_into_sections(blocks=blocks)
    return Document(
        source_length=len(body),
        sections=sections,
        toc=build_toc(sections=sections),
    )
