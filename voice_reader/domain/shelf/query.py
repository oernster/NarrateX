"""Narrowing and ordering a shelf: what the filter and the search actually mean.

FR-BS-042 to FR-BS-045, FR-BS-047 and FR-BS-053. Pure rules over works, with no
store and no clock. The caller supplies the works; for the recently-read
order it supplies the ordinals it holds. The shelf service then has nothing to decide,
which is the point; a filter that lives in a dialog is a filter nobody can test.

**A tick adds, a search narrows.** Two Horror ticks and a Fantasy tick show all
three; typing into the search then cuts that down. It reads the way Stellody's
filter reads; its dialog says so in one line: every tick adds to what is
shown.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from voice_reader.domain.shelf import text
from voice_reader.domain.shelf.works import Work


class Order(Enum):
    """How the shelf is laid out."""

    AUTHOR_THEN_TITLE = "author"
    TITLE = "title"
    RECENTLY_READ = "recent"


@dataclass(frozen=True, slots=True)
class ShelfQuery:
    """Everything the reader has asked of the shelf at one moment.

    `genres` empty and `include_ungenred` false means no genre filter at all,
    which is the cleared state (FR-BS-045). `include_ungenred` is separate
    because "states no genre" is a choice a reader makes, not a genre
    (FR-BS-044).
    """

    genres: frozenset[str] = field(default_factory=frozenset)
    include_ungenred: bool = False
    text: str = ""
    order: Order = Order.AUTHOR_THEN_TITLE

    @property
    def filters_by_genre(self) -> bool:
        return bool(self.genres) or self.include_ungenred

    @property
    def search(self) -> str:
        return self.text.strip().casefold()

    @property
    def narrows(self) -> bool:
        """True when this query shows less than the whole shelf.

        Asked by every caller that has to say "so many of so many", so the two
        ways of narrowing cannot drift apart: a shelf cut down by a search
        owes the reader the same sentence as one cut down by a tick.
        """

        return self.filters_by_genre or bool(self.search)


def matches_genre(work: Work, query: ShelfQuery) -> bool:
    """True when the genre part of the query admits this work."""

    if not query.filters_by_genre:
        return True
    carried = work.genres
    if not carried:
        return query.include_ungenred
    return any(genre in query.genres for genre in carried)


def matches_text(work: Work, query: ShelfQuery) -> bool:
    """True when the search text appears in the title or the author.

    Compared on the folded forms, so an accent or a full stop in an initial
    never hides a book from its own name.
    """

    wanted = query.search
    if not wanted:
        return True
    folded = text.fold_for_search(wanted)
    if not folded:
        return True
    haystack = f"{text.fold_for_search(work.title)} {text.fold_for_search(work.author)}"
    return folded in haystack


def matches(work: Work, query: ShelfQuery) -> bool:
    return matches_genre(work, query) and matches_text(work, query)


def apply(
    works: tuple[Work, ...],
    query: ShelfQuery,
    *,
    recency: Mapping[str, int] | None = None,
) -> tuple[Work, ...]:
    """The works this query admits, in the order it asks for.

    `recency` maps a book id to an ordinal, larger meaning more recently read.
    A work with no book id has never been opened, so it sorts after every work
    that has; within that group the default ordering decides, which keeps the
    result stable rather than arbitrary.
    """

    kept = tuple(work for work in works if matches(work, query))
    if query.order is Order.TITLE:
        return tuple(
            sorted(kept, key=lambda work: (text.title_key(work.title), work.sort_key))
        )
    if query.order is Order.RECENTLY_READ:
        seen = recency or {}

        def by_recency(work: Work) -> tuple[int, tuple[str, str]]:
            book_id = work.book_id
            ordinal = seen.get(book_id, 0) if book_id else 0
            return (-ordinal, work.sort_key)

        return tuple(sorted(kept, key=by_recency))
    return tuple(sorted(kept, key=lambda work: work.sort_key))


def genre_counts(works: tuple[Work, ...]) -> dict[str, int]:
    """How many works reach each genre, for the filter dialog to show."""

    counts: dict[str, int] = {}
    for work in works:
        for genre in work.genres:
            counts[genre] = counts.get(genre, 0) + 1
    return counts


def ungenred_count(works: tuple[Work, ...]) -> int:
    """How many works state no genre at all."""

    return sum(1 for work in works if not work.genres)
