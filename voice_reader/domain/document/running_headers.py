"""Page furniture that a conversion turned into body text.

A Kindle book carries the title as a running header on every page. Converting
it to EPUB has nowhere to put a page header, so the header becomes an ordinary
block at the top of each document and the narrator reads the title aloud once
per document. Measured on 2026-09-20 over `When the Wind Blows`: 128 of its 254
documents open with the title and 130 blocks are nothing else, so a listener
hears the title 130 times.

**A repeated lead alone is not enough.** Measured over eleven books in the
reference library, taking every text that leads more than one document would
also have taken a chapter opening ("Elsewhere,"), three chapter numbers and a
chapter name. Each of those led two or three documents out of dozens.

So a repeated lead is furniture when either of two things is also true of it.

**It is the book's own stated title.** That is what catches `When the Wind
Blows`, whose header leads 128 of its 254 documents and reads exactly as the
title does. With this condition the same measurement drops 130 blocks from that
book and nothing at all from the other ten.

**Or it leads most of the documents.** A header can word the title differently
and the first condition then misses it: `Fang: A Maximum Ride Novel` carries the
header "Maximum Ride 6 - Fang", which leads 93 of its 94 documents and matches
no title. Leading most of a book is furniture whatever it says; it is a
comparison rather than a proportion, so there is nothing to tune. The three
false positives above lead 3%, 9% and 0.8% of their books and stay prose.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

# Furniture runs through a book, so it appears at the head of more than one
# document. A title page on its own is a single lead and is left alone.
_LEADS_NEEDED = 2


def running_header(leads: Sequence[str], *, title: str | None) -> str | None:
    """The text being repeated as page furniture; None where there is none.

    `leads` is the first block of each document, in spine order.
    """

    counted = Counter(lead.strip() for lead in leads if lead.strip())
    if not counted:
        return None

    commonest, seen = counted.most_common(1)[0]
    if seen >= _LEADS_NEEDED and seen * 2 > len(leads):
        return commonest

    wanted = str(title or "").strip()
    if wanted and counted.get(wanted, 0) >= _LEADS_NEEDED:
        return wanted
    return None


def without_header(lines: Iterable[str], *, header: str | None) -> list[str]:
    """The lines of one document with every line that is only the header gone.

    A line is dropped only where the header is the whole of it. A sentence that
    happens to contain the title is prose and stays.
    """

    if not header:
        return list(lines)
    return [line for line in lines if line.strip() != header]
