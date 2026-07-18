"""Decide where the body of a book begins, from the document model.

`Document.body_start_offset` answers a narrower question: where the first
spoken block sits. That is usually the title page, so it is not where narration
should begin. This module answers the editorial question instead: past the
title page and the contents, where does the book actually start.

The contents section is located from the model's own `TOC_ENTRY` blocks rather
than by re-scanning the text. That matters: a contents page lists the very
heading names we are looking for, so searching from the top of the book finds
"Prologue" inside the contents rather than the real one. Starting the search
after the last contents entry is what avoids landing in the table itself.
"""

from __future__ import annotations

import re

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Document

# Sections that open the body proper. Matches the long-standing behaviour of
# the reading-start detector these rules replace.
_BODY_OPENINGS = frozenset(
    {
        "prologue",
        "introduction",
        "foreword",
        "preface",
        "acknowledgements",
        "acknowledgments",
    }
)

# Section titles that mark the contents itself.
_CONTENTS_TITLES = frozenset({"contents", "table of contents"})

# A numbered division also opens the body: "Chapter 1", "Part Two", "Book III".
_NUMBERED_DIVISION = re.compile(
    r"^(chapter|part|book|section|volume)\b[\s.:-]*\S",
    re.IGNORECASE,
)


def _is_body_opening(title: str) -> bool:
    stripped = str(title or "").strip()
    if not stripped:
        return False
    if stripped.rstrip(".").casefold() in _BODY_OPENINGS:
        return True
    return bool(_NUMBERED_DIVISION.match(stripped))


def _is_contents_title(title: str) -> bool:
    return str(title or "").strip().rstrip(".").casefold() in _CONTENTS_TITLES


def contents_end_offset(document: Document) -> int:
    """Offset just past the front matter's contents, or zero if there is none.

    Two kinds of evidence, because formats differ. A PDF contents page leaves
    dotted-leader entries behind, so its extent is the last of those. An EPUB
    contents is usually a plain list of links with no leaders at all, leaving
    no entries to find; there the evidence is a section actually titled
    "Contents". Using only the first would miss every EPUB.
    """

    ends = [
        block.source_end
        for block in document.blocks
        if block.kind is BlockKind.TOC_ENTRY
    ]
    ends += [
        section.source_end
        for section in document.sections
        if _is_contents_title(section.title)
    ]
    return max(ends) if ends else 0


def _first_spoken_offset_at_or_after(document: Document, offset: int) -> int | None:
    for block in document.blocks:
        if block.is_spoken and block.source_start >= offset:
            return block.source_start
    return None


def reading_start_offset(document: Document) -> int | None:
    """Offset at which narration should begin, or None when nothing is spoken.

    Falls back in steps rather than failing: a named body opening if one is
    found past the contents, otherwise the first spoken block past the
    contents, otherwise the first spoken block at all.
    """

    after_contents = contents_end_offset(document)

    for section in document.sections:
        if section.source_start < after_contents:
            continue
        if not _is_body_opening(section.title):
            continue
        for block in section.blocks:
            if block.is_spoken:
                return block.source_start

    past_contents = _first_spoken_offset_at_or_after(document, after_contents)
    if past_contents is not None:
        return past_contents
    return document.body_start_offset
