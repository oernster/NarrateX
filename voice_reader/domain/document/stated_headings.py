"""Headings taken from the book's own navigation, where it states none itself.

A Kindle book converted to EPUB frequently carries no heading tag anywhere: its
chapter names are ordinary paragraphs that merely look like headings. NarrateX
then sees one long unnamed section, so there is no chapter spine, no structural
bookmark and nothing to navigate by. Measured on 2026-09-20 over the reference
library: all ten real EPUBs state 14 to 242 headings of their own, while both
Kindle conversions state none at all.

**The book still says what its chapters are**, in the navigation every EPUB
carries. `When the Wind Blows` names 127 of them and `The Puppet Masters` 35; each
name also appears in the text exactly where the chapter begins. So the
names are not invented here: they are read from the book's own table and
matched to the book's own words.

Each name occurs twice, once in the contents list and once at the chapter. The
contents copy is already marked as such, so the chapter copy is the one left.

**It is a fallback, never an override.** A book that states even one heading of
its own is left exactly as it is, so nothing that works today can change. A book
whose navigation names fewer than two sections is left alone as well: there is
no spine to be had from one name, which is also what Calibre leaves behind when
the original carried no table of contents.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind

# The navigation is a flat list of names, so every heading taken from it sits
# at the top level. A book whose own tags express depth never reaches here.
_STATED_LEVEL = 1

# A spine needs two points before it divides anything, so one name is no spine.
# It is also the shape Calibre leaves when the source book carried no table of
# contents at all: a single entry reading "Start". Measured over eight Kindle
# books drawn at random from the library, four came out exactly that way; one
# of them holds a block whose words are "Start".
_NAMES_NEEDED = 2


def states_no_headings(drafts: Sequence[BlockDraft]) -> bool:
    """Whether the book failed to mark up a single heading of its own."""

    return not any(d.kind is BlockKind.HEADING for d in drafts)


def as_stated_headings(
    drafts: Sequence[BlockDraft], *, names: Iterable[str]
) -> list[BlockDraft]:
    """The drafts, with the blocks the navigation names read as headings."""

    wanted = {str(name).strip() for name in names if str(name).strip()}
    if len(wanted) < _NAMES_NEEDED or not states_no_headings(drafts):
        return list(drafts)
    return [
        (
            BlockDraft(kind=BlockKind.HEADING, text=d.text, level=_STATED_LEVEL)
            if d.kind is not BlockKind.TOC_ENTRY and d.text.strip() in wanted
            else d
        )
        for d in drafts
    ]
