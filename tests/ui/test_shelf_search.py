"""Typing narrows the shelf (FR-BS-047).

The rule itself is the domain's and is tested there; what these ask is whether
the field reaches it, whether it combines with the genre filter rather than
replacing it and whether the count says what a narrowed shelf is a part of.

A real `ShelfView` and a real `ShelfLibrary`, so the words read off the labels
are the words a reader would see.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.shelf import ShelfLibrary
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.genre_dialogs import GenreFilterDialog
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid
from voice_reader.ui.shelf_view import SEARCH_PLACEHOLDER

from tests.application.shelf.shelf_fakes import FakeBookmarks, FakeIndex, key

ROOT = Path("H:/Books")


def entry(path: str, title: str, author: str, *, subjects=()) -> ShelfEntry:
    return ShelfEntry(
        key=key(path), title=title, author=author, subjects=tuple(subjects)
    )


RAMA = entry("H:/Books/a.mobi", "Rendezvous with Rama", "Arthur C. Clarke")
ODYSSEY = entry("H:/Books/b.mobi", "2001: A Space Odyssey", "Arthur C. Clarke")
SHINING = entry("H:/Books/c.mobi", "The Shining", "Stephen King", subjects=("Horror",))
CARRIE = entry("H:/Books/d.mobi", "Carrie", "Stephen King", subjects=("Horror",))

EVERY_BOOK = (RAMA, ODYSSEY, SHINING, CARRIE)


class _Covers:
    def held_for(self, work) -> bytes | None:
        del work
        return None

    def thumbnail(self, work) -> bytes | None:
        del work
        return None


class _Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.covers = _Covers()
        self.scanner = None
        self.thumbnails = None


class _Controller:
    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None


def _controller(entries=EVERY_BOOK, *, stated=None):
    index = FakeIndex(roots=(ROOT,), entries=tuple(entries), stated=stated or {})
    shelf = _Shelf(ShelfLibrary(index=index, bookmarks=FakeBookmarks()))
    window = MainWindow()
    grid = ShelfGrid(covers=shelf.covers, parent=window.shelf_view)
    window.shelf_view.install_grid(grid)
    return _Controller(window, shelf)


def _titles(controller) -> list[str]:
    return [work.title for work in controller.window.shelf_view.grid.works()]


def test_the_field_says_what_it_is_for(qapp) -> None:
    del qapp
    controller = _controller()

    assert controller.window.shelf_view.txt_search.placeholderText() == (
        SEARCH_PLACEHOLDER
    )
    controller.window.shelf_view.grid.release()


def test_typing_an_author_narrows_the_shelf_to_them(qapp) -> None:
    """The acceptance in FR-BS-047, read off a real grid."""

    del qapp
    controller = _controller()

    shelf_helpers.search_shelf(controller, "clarke")

    assert sorted(_titles(controller)) == [
        "2001: A Space Odyssey",
        "Rendezvous with Rama",
    ]
    controller.window.shelf_view.grid.release()


def test_a_title_is_searched_as_well_as_an_author(qapp) -> None:
    del qapp
    controller = _controller()

    shelf_helpers.search_shelf(controller, "carrie")

    assert _titles(controller) == ["Carrie"]
    controller.window.shelf_view.grid.release()


def test_the_search_ignores_case(qapp) -> None:
    del qapp
    controller = _controller()

    shelf_helpers.search_shelf(controller, "RAMA")

    assert _titles(controller) == ["Rendezvous with Rama"]
    controller.window.shelf_view.grid.release()


def test_a_narrowed_shelf_says_what_it_is_a_part_of(qapp) -> None:
    """A reader who forgot they had typed is not left hunting for their books."""

    del qapp
    controller = _controller()

    shelf_helpers.search_shelf(controller, "clarke")

    assert controller.window.shelf_view.lbl_count.text() == "2 of 4 works"
    controller.window.shelf_view.grid.release()


def test_clearing_the_search_puts_every_book_back(qapp) -> None:
    del qapp
    controller = _controller()
    shelf_helpers.search_shelf(controller, "clarke")

    shelf_helpers.search_shelf(controller, "")

    assert len(_titles(controller)) == len(EVERY_BOOK)
    assert controller.window.shelf_view.lbl_count.text() == "4 works"
    controller.window.shelf_view.grid.release()


def test_a_search_matching_nothing_leaves_the_field_usable(qapp) -> None:
    """An empty answer is not an empty shelf; the words typed must be editable."""

    del qapp
    controller = _controller()

    shelf_helpers.search_shelf(controller, "asimov")

    view = controller.window.shelf_view
    assert _titles(controller) == []
    assert view.lbl_count.text() == "0 of 4 works"
    assert view.txt_search.isEnabled()
    view.grid.release()


def test_the_search_combines_with_the_genre_filter(qapp) -> None:
    """FR-BS-047 says combined with, not instead of."""

    del qapp
    controller = _controller()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.search_shelf(controller, "carrie")

    assert _titles(controller) == ["Carrie"]
    controller.window.shelf_view.grid.release()


def test_a_genre_that_excludes_the_typed_book_shows_nothing(qapp) -> None:
    del qapp
    controller = _controller()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.search_shelf(controller, "clarke")

    assert _titles(controller) == []
    controller.window.shelf_view.grid.release()


def test_the_typing_reaches_the_shelf_through_the_field(qapp) -> None:
    """The signal, not the helper: a field wired to nothing would pass above."""

    del qapp
    controller = _controller()
    view = controller.window.shelf_view
    view.search_changed.connect(
        lambda typed: shelf_helpers.search_shelf(controller, typed)
    )

    view.txt_search.setText("rama")

    assert _titles(controller) == ["Rendezvous with Rama"]
    view.grid.release()


def test_the_filter_dialog_keeps_what_was_typed(qapp) -> None:
    """Opening the filter and pressing Show must not wipe the search."""

    del qapp
    asked = ShelfQuery(text="clarke")
    dialog = GenreFilterDialog(asked, None)

    answered = dialog.query()

    assert answered.text == "clarke"
    dialog.deleteLater()
