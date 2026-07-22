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
from dataclasses import dataclass

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Document


@dataclass(frozen=True, slots=True)
class ReadingStart:
    """Where narration begins, and why, for the status line to report."""

    start_char: int
    reason: str


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


def _has_prose(section) -> bool:
    return any(block.kind is BlockKind.PARAGRAPH for block in section.blocks)


def _is_contents_title(title: str) -> bool:
    return str(title or "").strip().rstrip(".").casefold() in _CONTENTS_TITLES


def _body_began_at(document: Document) -> int | None:
    """Where the body demonstrably starts, or None if nothing shows it has.

    An opening section carrying actual prose is the demonstration. A contents
    page names the same sections but carries no prose under them, so it cannot
    satisfy this.
    """

    for section in document.sections:
        if _is_body_opening(section.title) and _has_prose(section):
            return section.source_start
    return None


def contents_end_offset(document: Document) -> int:
    """Offset just past the front matter's contents, or zero if there is none.

    Two kinds of evidence, because formats differ. A PDF contents page leaves
    dotted-leader entries behind, so its extent is the last of those. An EPUB
    contents is usually a plain list of links with no leaders at all, leaving
    no entries to find; there the evidence is a section actually titled
    "Contents". Using only the first would miss every EPUB.

    Evidence past the point where the body started is not front matter. Books
    carry back-of-book indexes and essay indexes that leave entries looking
    exactly like contents entries, and counting those would push the boundary
    over real sections and hide them.
    """

    limit = _body_began_at(document)

    def in_front_matter(start: int) -> bool:
        return limit is None or start < limit

    ends = [
        block.source_end
        for block in document.blocks
        if block.kind is BlockKind.TOC_ENTRY and in_front_matter(block.source_start)
    ]
    ends += [
        section.source_end
        for section in document.sections
        if _is_contents_title(section.title) and in_front_matter(section.source_start)
    ]
    return max(ends) if ends else 0


def _body_opening_sections(document: Document, *, after: int) -> list:
    """Sections at or past the contents that open the body.

    With a contents boundary, the body opens at the first section past it
    that carries prose, whatever its title. The pane shows everything past
    the contents, and a shown section must be spoken: an "About This
    Edition" between the contents and Book 1 was silently skipped when
    only recognised opening names counted. A leftover contents line
    wearing a section's title carries no prose, so the prose requirement
    still passes it over, and a stray section titled "Contents" itself is
    never an opening.

    Without a contents there is no boundary to anchor on, so the named
    openings remain the evidence, exactly as before: they are what stops
    narration starting on the title page.
    """

    if after <= 0:
        return [
            section for section in document.sections if _is_body_opening(section.title)
        ]

    past = [
        section
        for section in document.sections
        if section.source_start >= after and not _is_contents_title(section.title)
    ]
    with_prose = [section for section in past if _has_prose(section)]
    if with_prose:
        return with_prose
    return [section for section in past if _is_body_opening(section.title)]


def body_opening_offset(document: Document) -> int:
    """Offset of the heading that opens the body, or the contents end.

    Distinct from `reading_start_offset` on purpose. Navigation lands on the
    heading line, so it wants the heading's own offset; narration wants the
    first sentence under it. Using the narration offset as a navigation
    boundary would clamp the heading itself out of reach.
    """

    after_contents = contents_end_offset(document)
    openings = _body_opening_sections(document, after=after_contents)
    return openings[0].source_start if openings else after_contents


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

    for section in _body_opening_sections(document, after=after_contents):
        for block in section.blocks:
            if block.is_spoken:
                return block.source_start

    past_contents = _first_spoken_offset_at_or_after(document, after_contents)
    if past_contents is not None:
        return past_contents
    return document.body_start_offset
