"""Rules that need the whole library to answer, not one filename.

`Kurt Vonnegut - Bluebeard` and `Bluebeard - Kurt Vonnegut` are the same book
filed by two different hands; no amount of looking at either filename on its
own says which half is the author. Measured over the reference library on
2026-09-19, 216 of 2819 files put the author first with no comma to signal it,
which is enough to put visibly wrong tiles on a shelf: a work titled "Kurt
Vonnegut" by "Bluebeard".

What settles it is the rest of the library. A name standing in the author
position of fifty-eight other books is an author, wherever it sits in this one.

**Counting, not membership.** The first version of this rule asked whether each
half was a known author and swapped when exactly one was. It swapped almost
nothing, for a reason the library taught: these files are duplicated across two
folders, so a title wrongly read as an author is seen twice as well, which was
enough to make it "known" and block the swap. Weight decides it instead. "Neil
Gaiman" stands behind 58 books; "A Study in Emerald" stands behind 2. The
larger number is the author.

Pure: the corpus arrives as entries and leaves as entries. Nothing here reads a
file. It is a domain rule rather than an application one because it is a rule
about names; the scanner merely supplies the corpus.
"""

from __future__ import annotations

from voice_reader.domain.shelf import text
from voice_reader.domain.shelf.identity import ShelfEntry

# How many books a name must stand behind before the corpus will move it. One
# sighting is the name itself and proves nothing; a duplicated file gives two,
# so three is the smallest count that cannot be an accident of duplication.
MIN_SIGHTINGS = 3

# A single word is a surname, a series name or a magazine title with equal
# likelihood, so only complete names are counted.
MIN_NAME_WORDS = 2


def author_sightings(entries: tuple[ShelfEntry, ...]) -> dict[str, int]:
    """How many entries stand behind each author name the library states."""

    sightings: dict[str, int] = {}
    for entry in entries:
        if entry.author == text.UNKNOWN_AUTHOR:
            continue
        key = text.name_core(entry.author)
        if len(key.split()) < MIN_NAME_WORDS:
            continue
        sightings[key] = sightings.get(key, 0) + 1
    return sightings


def resolve_author_first(entries: tuple[ShelfEntry, ...]) -> tuple[ShelfEntry, ...]:
    """Swap title and author where the corpus says the title is the person.

    The swap needs the title's name to stand behind at least `MIN_SIGHTINGS`
    books and to stand behind strictly more of them than the author's string
    does. `The Mediterranean Caper - Clive Cussler` therefore stays as it is,
    because Clive Cussler outweighs the Caper by a wide margin.
    """

    sightings = author_sightings(entries)
    resolved: list[ShelfEntry] = []
    for entry in entries:
        as_author = sightings.get(text.name_core(entry.title), 0)
        as_written = sightings.get(text.name_core(entry.author), 0)
        if as_author >= MIN_SIGHTINGS and as_author > as_written:
            resolved.append(entry.with_metadata(title=entry.author, author=entry.title))
            continue
        resolved.append(entry)
    return tuple(resolved)
