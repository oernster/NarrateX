"""The shelf, its library and three works, as the genre suites drive them.

One home for them, because narrowing the shelf and filing a book are two
suites over the same shelf and a second copy of a fake drifts from the first
without anything failing to say so.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid

from tests.ui._fakes_shelf import Controller


def a_work(title: str, genres: tuple[str, ...] = ()) -> Work:
    key = ShelfKey(path=Path("H:/Books") / f"{title}.epub", size_bytes=1, modified_ns=1)
    entry = ShelfEntry(key=key, title=title, author="Somebody", subjects=())
    return Work(title=title, author="Somebody", entries=(entry,), stated_genres=genres)


DRACULA = a_work("Dracula", ("Horror",))
DUNE = a_work("Dune", ("Science Fiction",))
UNTAGGED = a_work("Untagged")
ALL = (DRACULA, DUNE, UNTAGGED)


class Library:
    """The shelf library, answering the three questions the filter asks."""

    def __init__(self, works: tuple[Work, ...] = ALL) -> None:
        self._works = works
        self.stated: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def roots(self) -> tuple[Path, ...]:
        return (Path("H:/Books"),)

    def works(self) -> tuple[Work, ...]:
        return self._works

    def view(self, query: ShelfQuery) -> tuple[Work, ...]:
        return tuple(
            work
            for work in self._works
            if (work.genres and set(work.genres) & query.genres)
            or (not work.genres and query.include_ungenred)
        )

    def state_genres(self, works, genres) -> None:
        self.stated.append((tuple(w.title for w in works), genres))


class Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.scanner = None
        self.covers = None
        self.thumbnails = None


def ready(works: tuple[Work, ...] = ALL):
    library = Library(works)
    controller = Controller(MainWindow(), Shelf(library))
    controller.window.shelf_view.install_grid(ShelfGrid())
    return controller, library


def shown(controller) -> list[str]:
    return [work.title for work in controller.window.shelf_view.grid.works()]
