"""The shelf a reader looks at: works, the filter over them and what they open.

FR-BS-011, FR-BS-042 to FR-BS-047, FR-BS-053 to FR-BS-055 and FR-BS-060. Every
rule is the domain's; this service holds the collaborators and the order of the
steps, so each reader-visible action has one named entry point that runs with
no window open.

**Progress is read, never stored.** NarrateX already keeps a resume position
per book id; a second store of "finished" would be a second truth able to
disagree with the first (DATA-BS-004).

**Forgetting keeps the tile.** The file is still on disk, so the work stays on
the shelf and reverts to unread (FR-BS-060). Only what NarrateX derived goes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.interfaces.bookmark_repository import BookmarkRepository
from voice_reader.domain.interfaces.shelf_ports import ShelfIndexRepository
from voice_reader.domain.shelf import progress as progress_rules
from voice_reader.domain.shelf import query as query_rules
from voice_reader.domain.shelf import roots as root_rules
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.progress import Progress
from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.domain.shelf.works import Work, gather, possible_duplicates


@dataclass(frozen=True, slots=True)
class RootOutcome:
    """What happened when a reader nominated a folder (FR-BS-001c)."""

    roots: tuple[Path, ...]
    added: bool
    covered_by: Path | None = None
    replaced: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class ShelfLibrary:
    """Reads the index, answers the shelf, records what the reader states."""

    index: ShelfIndexRepository
    bookmarks: BookmarkRepository

    # Roots -----------------------------------------------------------------

    def roots(self) -> tuple[Path, ...]:
        return self.index.load_roots()

    def add_root(self, candidate: Path) -> RootOutcome:
        """Nominate a folder, refusing one already covered by another."""

        current = self.roots()
        covering = root_rules.covering(current, candidate)
        if covering is not None:
            return RootOutcome(roots=current, added=False, covered_by=covering)
        replaced = root_rules.covered_by(current, candidate)
        updated = root_rules.added(current, candidate)
        self.index.save_roots(updated)
        return RootOutcome(roots=updated, added=True, replaced=replaced)

    def remove_root(self, unwanted: Path) -> tuple[Path, ...]:
        """Drop a root and every entry found only beneath it (FR-BS-001b)."""

        updated = root_rules.removed(self.roots(), unwanted)
        self.index.save_roots(updated)
        kept = tuple(
            entry
            for entry in self.index.load_entries()
            if root_rules.covering(updated, entry.key.path) is not None
        )
        self.index.save_entries(kept)
        return updated

    # The shelf -------------------------------------------------------------

    def works(self) -> tuple[Work, ...]:
        """Every work the index holds, carrying what the reader has stated."""

        entries = self.index.load_entries()
        stated = self.index.load_stated_genres()
        folded = gather(entries)
        if not stated:
            return folded
        return tuple(
            Work(
                title=work.title,
                author=work.author,
                entries=work.entries,
                stated_genres=stated.get(work.token, ()),
            )
            for work in folded
        )

    def view(self, query: ShelfQuery) -> tuple[Work, ...]:
        """The works this query admits, in the order it asks for."""

        works = self.works()
        recency = (
            self._recency(works)
            if query.order is query_rules.Order.RECENTLY_READ
            else None
        )
        return query_rules.apply(works, query, recency=recency)

    def genre_counts(self) -> dict[str, int]:
        return query_rules.genre_counts(self.works())

    def ungenred_count(self) -> int:
        return query_rules.ungenred_count(self.works())

    def unmatched_subjects(self) -> tuple[str, ...]:
        """Every subject the catalogue did not recognise (FR-BS-041)."""

        seen: dict[str, None] = {}
        for work in self.works():
            for subject in work.reading.unmatched:
                seen.setdefault(subject, None)
        return tuple(seen)

    def duplicates(self) -> frozenset[tuple[str, str]]:
        return possible_duplicates(self.works())

    # One work --------------------------------------------------------------

    def progress_of(self, work: Work) -> Progress:
        """How far through this work the reader is (FR-BS-054)."""

        book_id, total = work.book_id, self._total_chars(work)
        if book_id is None or not total:
            return progress_rules.UNREAD
        position = self.bookmarks.load_resume_position(book_id=book_id)
        if position is None:
            return progress_rules.UNREAD
        return progress_rules.of(position.char_offset / total)

    def path_to_open(self, work: Work) -> Path:
        """The file this work opens: the cheapest format it holds."""

        return work.preferred.key.path

    def record_reading_identity(
        self, work: Work, *, book_id: str, total_chars: int
    ) -> None:
        """Join a work to its narration identity, once it has been opened."""

        updated: list[ShelfEntry] = []
        wanted = {entry.key.path for entry in work.entries}
        for entry in self.index.load_entries():
            if entry.key.path in wanted:
                entry = entry.with_book_id(book_id, total_chars=total_chars)
            updated.append(entry)
        self.index.save_entries(tuple(updated))

    def state_genres(self, works: tuple[Work, ...], genres: tuple[str, ...]) -> None:
        """File these works under these genres, outranking the files."""

        stated = dict(self.index.load_stated_genres())
        for work in works:
            if genres:
                stated[work.token] = genres
            else:
                stated.pop(work.token, None)
        self.index.save_stated_genres(stated)

    def forget(self, work: Work) -> None:
        """Drop what NarrateX derived, leaving the tile and the file alone."""

        book_id = work.book_id
        if book_id is not None:
            self.bookmarks.delete_book(book_id=book_id)
        wanted = {entry.key.path for entry in work.entries}
        cleared = tuple(
            (
                ShelfEntry(
                    key=entry.key,
                    title=entry.title,
                    author=entry.author,
                    subjects=entry.subjects,
                    has_cover=entry.has_cover,
                )
                if entry.key.path in wanted
                else entry
            )
            for entry in self.index.load_entries()
        )
        self.index.save_entries(cleared)

    # Internals -------------------------------------------------------------

    @staticmethod
    def _total_chars(work: Work) -> int | None:
        for entry in work.entries:
            if entry.total_chars:
                return entry.total_chars
        return None

    def _recency(self, works: tuple[Work, ...]) -> dict[str, int]:
        """A book id to an ordinal, larger meaning more recently read."""

        stamped: list[tuple[float, str]] = []
        for work in works:
            book_id = work.book_id
            if book_id is None:
                continue
            position = self.bookmarks.load_resume_position(book_id=book_id)
            if position is None:
                continue
            stamped.append((position.updated_at.timestamp(), book_id))
        stamped.sort()
        return {book_id: rank + 1 for rank, (_when, book_id) in enumerate(stamped)}
