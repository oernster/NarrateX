"""Narrowing the shelf by genre; filing a book under one.

FR-BS-042 to FR-BS-046. Real widgets against a real QApplication, with the
library standing in, because what is asserted is which works reach the grid.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.domain.shelf.works import Work
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid

from tests.ui._fakes_shelf import Controller


def _work(title: str, genres: tuple[str, ...] = ()) -> Work:
    key = ShelfKey(path=Path("H:/Books") / f"{title}.epub", size_bytes=1, modified_ns=1)
    entry = ShelfEntry(key=key, title=title, author="Somebody", subjects=())
    return Work(title=title, author="Somebody", entries=(entry,), stated_genres=genres)


DRACULA = _work("Dracula", ("Horror",))
DUNE = _work("Dune", ("Science Fiction",))
UNTAGGED = _work("Untagged")
ALL = (DRACULA, DUNE, UNTAGGED)


class _Library:
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


class _Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.scanner = None
        self.covers = None
        self.thumbnails = None


def _ready(works: tuple[Work, ...] = ALL):
    library = _Library(works)
    controller = Controller(MainWindow(), _Shelf(library))
    controller.window.shelf_view.install_grid(ShelfGrid())
    return controller, library


def _shown(controller) -> list[str]:
    return [work.title for work in controller.window.shelf_view.grid.works()]


# Narrowing the shelf --------------------------------------------------------


def test_with_no_filter_the_whole_shelf_is_shown(qapp) -> None:
    del qapp
    controller, _library = _ready()

    shelf_helpers.refresh_shelf(controller)

    assert _shown(controller) == ["Dracula", "Dune", "Untagged"]
    assert controller.window.shelf_view.lbl_count.text() == "3 works"


def test_a_ticked_genre_narrows_the_shelf_to_it(qapp) -> None:
    """FR-BS-042."""

    del qapp
    controller, _library = _ready()

    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    assert _shown(controller) == ["Dracula"]


def test_the_count_says_a_filter_is_narrowing_the_shelf(qapp) -> None:
    """A reader who forgot the filter is not left wondering where books went."""

    del qapp
    controller, _library = _ready()

    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    assert controller.window.shelf_view.lbl_count.text() == "1 of 3 works"


def test_the_no_genre_choice_reaches_works_carrying_none(qapp) -> None:
    """FR-BS-044."""

    del qapp
    controller, _library = _ready()

    shelf_helpers.apply_shelf_query(controller, ShelfQuery(include_ungenred=True))

    assert _shown(controller) == ["Untagged"]


def test_clearing_the_filter_shows_everything_again(qapp) -> None:
    """FR-BS-045."""

    del qapp
    controller, _library = _ready()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.apply_shelf_query(controller, ShelfQuery())

    assert _shown(controller) == ["Dracula", "Dune", "Untagged"]
    assert controller.window.shelf_view.lbl_count.text() == "3 works"


def test_the_filter_is_remembered_across_a_refresh(qapp) -> None:
    del qapp
    controller, _library = _ready()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.refresh_shelf(controller)

    assert _shown(controller) == ["Dracula"]


def test_a_shelf_asked_for_nothing_yet_asks_for_everything(qapp) -> None:
    del qapp
    controller, _library = _ready()

    assert shelf_helpers.shelf_query(controller) == ShelfQuery()


def test_a_controller_holding_rubbish_still_asks_for_everything(qapp) -> None:
    """Never lock a reader out of their shelf over a state read gone odd."""

    del qapp
    controller, _library = _ready()
    controller._shelf_query = "not a query"  # noqa: SLF001

    assert shelf_helpers.shelf_query(controller) == ShelfQuery()


def test_opening_the_filter_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.filter_shelf(controller)


def test_the_filter_control_is_offered_only_once_there_is_a_shelf(qapp) -> None:
    del qapp
    controller, _library = _ready()
    view = controller.window.shelf_view

    assert view.btn_filter.isEnabled() is False
    shelf_helpers.refresh_shelf(controller)
    assert view.btn_filter.isEnabled() is True


def test_the_filter_shuts_again_when_there_is_nothing_to_narrow(qapp) -> None:
    del qapp
    controller, _library = _ready(works=())
    shelf_helpers.refresh_shelf(controller)

    assert controller.window.shelf_view.btn_filter.isEnabled() is False


# Filing a book --------------------------------------------------------------


def test_the_reader_statement_reaches_the_library(qapp) -> None:
    """FR-BS-046."""

    del qapp
    controller, library = _ready()

    shelf_helpers.state_work_genres(controller, UNTAGGED, ("Horror",))

    assert library.stated == [(("Untagged",), ("Horror",))]


def test_an_empty_statement_withdraws_the_reader_s_filing(qapp) -> None:
    del qapp
    controller, library = _ready()

    shelf_helpers.state_work_genres(controller, DRACULA, ())

    assert library.stated == [(("Dracula",), ())]


def test_filing_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.state_work_genres(controller, DRACULA, ("Horror",))
    shelf_helpers.tag_work(controller, DRACULA)


def test_asking_to_file_a_work_opens_nothing_in_the_suite(qapp) -> None:
    """A modal exec would hang the suite; the outcome is driven directly."""

    del qapp
    controller, library = _ready()

    shelf_helpers.tag_work(controller, DRACULA)

    assert library.stated == []


def test_opening_the_filter_with_a_shelf_builds_the_dialog(qapp) -> None:
    """It gets as far as the dialog; the modal itself is not opened here."""

    del qapp
    controller, library = _ready()

    shelf_helpers.filter_shelf(controller)

    assert library.stated == []


def test_the_right_button_over_a_tile_offers_to_file_that_work(qapp) -> None:
    """FR-BS-046, reached the way a reader reaches it."""

    del qapp
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent

    controller, _library = _ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    grid.resize(600, 400)
    asked: list[Work] = []
    grid.tag_requested.connect(asked.append)

    spot = grid.visualRect(grid.model().index(0, 0)).center()
    grid.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, spot, QPoint(0, 0))
    )
    # The menu itself is modal, so the press is made on the action it offers.
    menu = grid.menu_for(DRACULA)
    assert menu.actions()[0].text() == "File Dracula under a genre"
    menu.actions()[0].trigger()

    assert [work.title for work in asked] == ["Dracula"]


def test_the_right_button_away_from_every_tile_offers_nothing(qapp) -> None:
    del qapp
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent

    controller, _library = _ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    grid.resize(600, 400)
    asked: list[Work] = []
    grid.tag_requested.connect(asked.append)

    grid.contextMenuEvent(
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse, QPoint(590, 390), QPoint(0, 0)
        )
    )

    assert asked == []


def test_the_controller_offers_both_acts_as_methods(qapp) -> None:
    """The grid and the button connect to names, so the names must exist."""

    del qapp
    from voice_reader.ui._ui_controller_shelf_api import ShelfApi

    class _Api(ShelfApi):
        def __init__(self, window, shelf) -> None:
            self.window = window
            self.shelf = shelf
            self._shelf_scan_thread = None

    controller, library = _ready()
    api = _Api(controller.window, controller.shelf)

    api.filter_shelf()
    api.tag_work(DRACULA)

    assert library.stated == []
