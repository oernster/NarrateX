"""Hand-written stand-ins the shelf tests share.

One home for them, because three suites drive the same controller helpers and a
second copy of a fake drifts from the first without anything failing to say so.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf import query as query_rules
from voice_reader.domain.shelf.works import Work


def a_work(
    name: str = "Dune - Frank Herbert.epub", *, root: Path | None = None
) -> Work:
    """A work named by its file, so two files are two works.

    The title and the author are read off the stem rather than fixed: a work is
    keyed on those, so a helper that hardcoded them would hand back the same work
    under two filenames and quietly defeat any test about two of them.
    """

    path = (root or Path("H:/Books")) / name
    title, _, author = path.stem.partition(" - ")
    key = ShelfKey(path=path, size_bytes=1, modified_ns=1)
    entry = ShelfEntry(key=key, title=title, author=author)
    return Work(title=title, author=author, entries=(entry,))


class Library:
    """The shelf library, as the controller helpers ask it."""

    def __init__(self, path: Path, works: tuple[Work, ...] = ()) -> None:
        self._path = path
        self._works = works
        self.recorded: list[tuple[str, int]] = []

    def path_to_open(self, asked: Work) -> Path:
        del asked
        return self._path

    def roots(self) -> tuple[Path, ...]:
        return (self._path.parent,)

    def works(self) -> tuple[Work, ...]:
        return self._works

    def view_of(self, works: tuple[Work, ...], query) -> tuple[Work, ...]:
        """The real rule, so this fake cannot pass while the rule is wrong."""

        return query_rules.apply(works, query)


class Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.scanner = None
        self.covers = None
        self.thumbnails = None


class Controller:
    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None
        self.prepared = 0
        self.loaded: list[Path] = []


class Engine:
    """The narration service, as the shelf asks it: one state, nothing more."""

    def __init__(self, status: NarrationStatus) -> None:
        self.state = NarrationState(
            status=status, current_chunk_id=None, total_chunks=None, progress=0.0
        )
