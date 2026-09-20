"""Page furniture that a conversion turned into body text.

A Kindle book carries the title as a running header on every page. Converting
it to EPUB has nowhere to put a page header, so the header becomes an ordinary
block at the top of each document and the narrator reads the title aloud once
per document. Measured on 2026-09-20 over `When the Wind Blows`: 128 of its 254
documents open with the title and 130 blocks are nothing else, so a listener
hears the title 130 times.

**Two conditions, both structural, because one alone is not safe.** A text that
merely leads more than one document is not enough: measured over eleven books
in the reference library, that alone would also have taken a chapter opening
("Elsewhere,"), three chapter numbers and a chapter name. What makes a repeated
lead furniture rather than prose is that it is the book's own stated title.
With both conditions the same measurement drops 130 blocks from the affected
book and nothing at all from the other ten.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# Furniture runs through a book, so it appears at the head of more than one
# document. A title page on its own is a single lead and is left alone.
_LEADS_NEEDED = 2


def running_header(leads: Sequence[str], *, title: str | None) -> str | None:
    """The text being repeated as page furniture; None where there is none.

    `leads` is the first block of each document, in spine order.
    """

    if not title:
        return None
    wanted = title.strip()
    if not wanted:
        return None
    seen = sum(1 for lead in leads if lead.strip() == wanted)
    return wanted if seen >= _LEADS_NEEDED else None


def without_header(lines: Iterable[str], *, header: str | None) -> list[str]:
    """The lines of one document with every line that is only the header gone.

    A line is dropped only where the header is the whole of it. A sentence that
    happens to contain the title is prose and stays.
    """

    if not header:
        return list(lines)
    return [line for line in lines if line.strip() != header]
