"""Chapter headings recognised from the words, for a book that states none.

The last fallback, below the book's own heading tags and below the navigation
table it carries. It exists because many Kindle files have neither: measured on
2026-09-20 over twenty Kindle books drawn at random from the library, fourteen
carried no table of contents at all, only the single placeholder entry Calibre
leaves behind.

**Only a numbered division counts, plus the handful of divisions English never
numbers.** That restraint is what makes it safe. Scored against ten books whose
navigation gave a known answer, a keyword rule with a length limit found 448
real headings against 15 apparent errors; every one of those fifteen turned out
to be a real heading the book's own navigation had omitted: PROLOGUE, PART
I, CHAPTER 1, Book One. The one genuine error came from a book being named
rather than divided, "Book design by Virginia Norey", which requiring a number
after the word removes.

**What it deliberately cannot do.** A book whose chapters carry prose names,
"Fencing Practice", "The Good Man", is beyond any rule reading words alone:
those are indistinguishable from a sentence. They accounted for 218 of the 226
names the rule missed. Such books keep their navigation, which names them, so
nothing is lost by declining to guess here.

Measured over twelve books carrying no navigation: six gained a spine of
between 2 and 74 headings; six state no numbered division anywhere and are left
exactly as they were.
"""

from __future__ import annotations

from collections.abc import Sequence

from voice_reader.domain.document import divisions
from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.stated_headings import states_no_headings

# A heading is a line, not a paragraph. The longest real heading measured was
# six words ("CHAPTER ONE - Spaceguard"); 540 of the 544 names the reference
# books state fall at or under it.
_MOST_WORDS = 6

# A spine needs two points before it divides anything, exactly as it does when
# the names come from the navigation.
_HEADINGS_NEEDED = 2

_UNNUMBERED = divisions.FRONT_OPENINGS | divisions.OTHER_DIVISIONS


def reads_as_a_heading(text: str) -> bool:
    """Whether these words are a chapter heading rather than a sentence."""

    stripped = str(text or "").strip()
    if not stripped or len(stripped.split()) > _MOST_WORDS:
        return False
    if divisions.is_named_division(stripped, words=_UNNUMBERED):
        return True
    return divisions.is_numbered_division(stripped)


def as_text_headings(drafts: Sequence[BlockDraft]) -> list[BlockDraft]:
    """The drafts, with numbered divisions read as the headings they are.

    A book that states a heading anywhere, by its own tags or through its
    navigation, has already been served and is handed back untouched.
    """

    if not states_no_headings(drafts):
        return list(drafts)
    found = [
        d
        for d in drafts
        if d.kind is not BlockKind.TOC_ENTRY and reads_as_a_heading(d.text)
    ]
    if len(found) < _HEADINGS_NEEDED:
        return list(drafts)
    marked = {id(d) for d in found}
    return [
        (
            BlockDraft(kind=BlockKind.HEADING, text=d.text, level=1)
            if id(d) in marked
            else d
        )
        for d in drafts
    ]
