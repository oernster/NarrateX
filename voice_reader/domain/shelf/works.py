"""One book as a reader thinks of it, gathered from the files that hold it.

FR-BS-012, FR-BS-013 and FR-BS-014. The reference library holds roughly 717
books twice, once as `.mobi` under one folder and once as `.azw3` under
another, with identical stems. Drawn as files, half the shelf is a duplicate of
the other half; drawn as works, it is a library.

**Two files are one work when they fold to the same title and author.** The
folding is in `text`; it is deliberately generous about the things a library
is inconsistent about: the position of an article, a missing full stop
in an initial, a surname written first, an underscore standing in for a colon,
a `(2)` marking a second download.

**Two works that merely look alike are left apart.** `Aquaintaine Progession,
The` and `The Acquitaine Progression` are the same novel and one of them is
typed wrong; no rule can know that without guessing; a wrong guess loses a
book from the shelf entirely. So the rule here is conservative: a possible
duplicate is MARKED, never merged; the reader decides.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.shelf import genres as genre_rules
from voice_reader.domain.shelf import text
from voice_reader.domain.shelf.identity import ShelfEntry


@dataclass(frozen=True, slots=True)
class Work:
    """Every file that holds one book, with the reading of its subjects."""

    title: str
    author: str
    entries: tuple[ShelfEntry, ...]
    stated_genres: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("a work needs at least one entry")

    @property
    def key(self) -> tuple[str, str]:
        return (text.title_key(self.title), text.name_core(self.author))

    @property
    def preferred(self) -> ShelfEntry:
        """The entry to open: cheapest format first (FR-BS-013).

        Ties break on the path, so the answer never depends on the order the
        filesystem happened to walk the folders in.
        """

        return min(
            self.entries,
            key=lambda entry: (entry.preference_rank, entry.key.path.as_posix()),
        )

    @property
    def book_id(self) -> str | None:
        """The narration identity, once any entry of this work has one."""

        for entry in self.entries:
            if entry.book_id is not None:
                return entry.book_id
        return None

    @property
    def has_cover(self) -> bool:
        return any(entry.has_cover for entry in self.entries)

    @property
    def cover_candidates(self) -> tuple[ShelfEntry, ...]:
        """Which of this work's files to ask for a cover, in order.

        A file that the scan saw state a cover comes first, then the cheapest
        format. A work held as both an EPUB and a Kindle file is opened from the
        EPUB (FR-BS-013) while its cover may only exist in the Kindle header, so
        the file to read the picture from is not always the file to read the
        book from.
        """

        return tuple(
            sorted(
                self.entries,
                key=lambda entry: (
                    not entry.has_cover,
                    entry.preference_rank,
                    entry.key.path.as_posix(),
                ),
            )
        )

    @property
    def formats(self) -> tuple[str, ...]:
        return tuple(sorted({entry.suffix for entry in self.entries}))

    @property
    def reading(self) -> genre_rules.GenreReading:
        """Every genre this work's files state, read through the catalogue."""

        subjects: list[str] = []
        for entry in self.entries:
            subjects.extend(entry.subjects)
        return genre_rules.read(tuple(subjects))

    @property
    def genres(self) -> tuple[str, ...]:
        """What the work is filed under: the reader's word where they gave one.

        FR-BS-046: a reader statement outranks anything read from the file;
        it replaces rather than adds to it, since a correction that leaves the
        wrong answer in place has corrected nothing.
        """

        if self.stated_genres:
            return tuple(sorted(genre_rules.with_mains(frozenset(self.stated_genres))))
        return self.reading.genres

    def carries(self, genre: str) -> bool:
        return genre in self.genres

    @property
    def sort_key(self) -> tuple[str, str]:
        return text.sort_key(self.title, self.author)

    @property
    def token(self) -> str:
        """A stable string naming this work, for a store to key on.

        Built from the comparison forms rather than from a path, so a book
        moved on disk keeps whatever the reader stated about it.
        """

        return f"{self.key[1]}|{self.key[0]}"


def gather(entries: tuple[ShelfEntry, ...]) -> tuple[Work, ...]:
    """Every entry folded into the works they belong to.

    The title and author shown are taken from the entry whose format is
    preferred, so a work spelled two ways shows the spelling of the file that
    will actually be opened.
    """

    grouped: dict[tuple[str, str], list[ShelfEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.work_key, []).append(entry)

    works: list[Work] = []
    for members in grouped.values():
        ordered = tuple(
            sorted(
                members,
                key=lambda entry: (entry.preference_rank, entry.key.path.as_posix()),
            )
        )
        leader = ordered[0]
        works.append(Work(title=leader.title, author=leader.author, entries=ordered))
    return tuple(sorted(works, key=lambda work: work.sort_key))


def possible_duplicates(works: tuple[Work, ...]) -> frozenset[tuple[str, str]]:
    """Pairs of works that may be the same book (FR-BS-014).

    The test is deliberately narrow: the same author, plus one title reading
    as the opening of the other. That catches a subtitle added to one copy and
    nothing else. It will not catch a misspelling, which is stated as a limit
    rather than papered over with a similarity threshold nobody can defend.
    """

    by_author: dict[str, list[Work]] = {}
    for work in works:
        by_author.setdefault(text.name_core(work.author), []).append(work)

    pairs: set[tuple[str, str]] = set()
    for author_works in by_author.values():
        for index, first in enumerate(author_works):
            for second in author_works[index + 1 :]:
                if _one_opens_the_other(first, second):
                    left, right = first.token, second.token
                    pairs.add((left, right) if left <= right else (right, left))
    return frozenset(pairs)


def _one_opens_the_other(first: Work, second: Work) -> bool:
    left, right = text.title_key(first.title), text.title_key(second.title)
    if left == right or not left or not right:
        return False
    shorter, longer = sorted((left, right), key=len)
    return longer.startswith(shorter + " ")
