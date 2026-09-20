"""Filing a book under a genre, one at a time or several at once.

FR-BS-046, FR-BS-046a and FR-BS-046b. Real widgets against a real
QApplication, with the library standing in, because what is asserted is what
reaches it.
"""

from __future__ import annotations

from voice_reader.domain.shelf.works import Work
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow

from tests.ui._fakes_genres import DRACULA, DUNE, UNTAGGED, a_work, ready
from tests.ui._fakes_shelf import Controller

# Filing a book --------------------------------------------------------------


def test_the_reader_statement_reaches_the_library(qapp) -> None:
    """FR-BS-046."""

    del qapp
    controller, library = ready()

    shelf_helpers.state_work_genres(controller, (UNTAGGED,), ("Horror",))

    assert library.stated == [(("Untagged",), ("Horror",))]


def test_an_empty_statement_withdraws_the_reader_s_filing(qapp) -> None:
    del qapp
    controller, library = ready()

    shelf_helpers.state_work_genres(controller, (DRACULA,), ())

    assert library.stated == [(("Dracula",), ())]


def test_filing_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.state_work_genres(controller, (DRACULA,), ("Horror",))
    shelf_helpers.tag_work(controller, (DRACULA,))


def test_asking_to_file_a_work_opens_nothing_in_the_suite(qapp) -> None:
    """A modal exec would hang the suite; the outcome is driven directly."""

    del qapp
    controller, library = ready()

    shelf_helpers.tag_work(controller, (DRACULA,))

    assert library.stated == []


def test_opening_the_filter_with_a_shelf_builds_the_dialog(qapp) -> None:
    """It gets as far as the dialog; the modal itself is not opened here."""

    del qapp
    controller, library = ready()

    shelf_helpers.filter_shelf(controller)

    assert library.stated == []


def test_the_right_button_over_a_tile_offers_to_file_that_work(qapp) -> None:
    """FR-BS-046, reached the way a reader reaches it."""

    del qapp
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent

    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    grid.resize(600, 400)
    asked: list[tuple] = []
    grid.tag_requested.connect(asked.append)

    spot = grid.visualRect(grid.model().index(0, 0)).center()
    grid.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, spot, QPoint(0, 0))
    )
    # The menu itself is modal, so the press is made on the action it offers.
    menu = grid.menu_for((DRACULA,))
    assert menu.actions()[0].text() == "File Dracula under a genre"
    menu.actions()[0].trigger()

    assert [[w.title for w in group] for group in asked] == [["Dracula"]]


def test_the_right_button_away_from_every_tile_offers_nothing(qapp) -> None:
    del qapp
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent

    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    grid.resize(600, 400)
    asked: list[tuple] = []
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

    controller, library = ready()
    api = _Api(controller.window, controller.shelf)

    api.filter_shelf()
    api.tag_work((DRACULA,))

    assert library.stated == []


# Several at once (FR-BS-046a) ----------------------------------------------


def _gather(grid, rows: tuple[int, ...]) -> None:
    from PySide6.QtCore import QItemSelectionModel

    chooser = grid.selectionModel()
    for row in rows:
        chooser.select(
            grid.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select
        )


def test_the_gathered_works_read_in_the_order_the_shelf_shows_them(qapp) -> None:
    """The selection remembers click order, which nobody can see."""

    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid

    _gather(grid, (2, 0))

    assert [work.title for work in grid.selected_works()] == ["Dracula", "Untagged"]


def test_a_right_click_on_a_gathered_tile_is_about_all_of_them(qapp) -> None:
    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    _gather(grid, (0, 1))

    assert [w.title for w in grid.works_to_file(DRACULA)] == ["Dracula", "Dune"]


def test_a_right_click_away_from_the_gathering_is_about_that_tile_alone(
    qapp,
) -> None:
    """A stale selection elsewhere must not be filed by accident."""

    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    _gather(grid, (0, 1))

    assert [w.title for w in grid.works_to_file(UNTAGGED)] == ["Untagged"]


def test_one_gathered_tile_is_still_about_that_tile(qapp) -> None:
    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    _gather(grid, (0,))

    assert [w.title for w in grid.works_to_file(DRACULA)] == ["Dracula"]


def test_the_menu_counts_the_books_rather_than_naming_them_all(qapp) -> None:
    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid

    menu = grid.menu_for((DRACULA, DUNE))

    assert menu.actions()[0].text() == "File these 2 books under a genre"


def test_filing_several_reaches_the_library_as_one_statement(qapp) -> None:
    """FR-BS-046a."""

    del qapp
    controller, library = ready()

    shelf_helpers.state_work_genres(controller, (DRACULA, DUNE), ("Horror",))

    assert library.stated == [(("Dracula", "Dune"), ("Horror",))]


def test_the_dialog_opens_on_what_they_all_already_agree_on(qapp) -> None:
    """Ticking replaces, so opening on a genre only one carries would lie."""

    both = a_work("Both", ("Horror", "Science Fiction"))

    assert shelf_helpers.shared_genres((DRACULA, both)) == ("Horror",)
    assert shelf_helpers.shared_genres((DRACULA, DUNE)) == ()
    assert shelf_helpers.shared_genres(()) == ()


def test_the_dialog_says_how_many_it_is_about(qapp) -> None:
    del qapp

    assert shelf_helpers.filing_words((DRACULA,)) == "Dracula"
    assert shelf_helpers.filing_words((DRACULA, DUNE)) == "2 books"


def test_filing_nothing_at_all_does_nothing(qapp) -> None:
    del qapp
    controller, library = ready()

    shelf_helpers.tag_work(controller, ())

    assert library.stated == []


def test_a_plain_click_opens_the_book(qapp) -> None:
    del qapp
    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    grid._on_activated(grid.model().index(0, 0))  # noqa: SLF001

    assert [work.title for work in opened] == ["Dracula"]


def test_a_click_holding_a_modifier_gathers_rather_than_opens(
    qapp, monkeypatch
) -> None:
    """Both reach `clicked`, so the modifier is what tells them apart."""

    del qapp
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    controller, _library = ready()
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    for held in (
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.ShiftModifier,
    ):
        monkeypatch.setattr(
            QApplication, "keyboardModifiers", staticmethod(lambda h=held: h)
        )
        grid._on_activated(grid.model().index(0, 0))  # noqa: SLF001

    assert opened == []
