"""The shelf as a view of the main window; the control that shows it.

Real widgets against a real QApplication throughout; Qt is never mocked. The
library behind the view is a hand-written stand-in, because what is under test
is what the reader sees rather than what the index holds.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.ui import shelf_view as shelf_view_module
from voice_reader.ui._ui_controller_shelf import refresh_shelf, toggle_shelf
from voice_reader.ui.artwork import Artwork
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_view import ShelfView


class _FakeLibrary:
    def __init__(self, roots=(), works=()) -> None:
        self._roots = tuple(roots)
        self._works = tuple(works)

    def roots(self):
        return self._roots

    def works(self):
        return self._works


class _FakeController:
    """Only what the shelf helpers reach for."""

    def __init__(self, window, library=None) -> None:
        self.window = window
        self.shelf = None if library is None else _FakeShelf(library)


class _FakeShelf:
    def __init__(self, library) -> None:
        self.library = library
        self.scanner = None
        self.thumbnails = None


# The window ------------------------------------------------------------------


def test_the_shelf_control_sits_beside_the_open_control(qapp) -> None:
    """FR-BS-056a: a control that shows the shelf, with the picker kept."""

    del qapp
    window = MainWindow()

    assert window.btn_shelf.toolTip(), "the control must say what it does"
    assert not window.btn_shelf.icon().isNull(), "the bookshelf artwork is missing"
    assert window.btn_select_book is not None, "the picker stays; see FR-BS-056a"
    ring = []
    stop = window.btn_select_book
    for _ in range(3):
        ring.append(stop)
        stop = stop.nextInFocusChain()
    assert window.btn_shelf in ring, "the shelf control follows the picker in the ring"


def test_the_window_starts_on_the_reader_and_the_control_swaps_views(qapp) -> None:
    """FR-BS-050a: one window, two pages."""

    del qapp
    window = MainWindow()

    assert not window.showing_shelf()
    window.show_shelf_view()
    assert window.showing_shelf()
    window.show_reader_view()
    assert not window.showing_shelf()


def test_no_container_on_the_shelf_takes_a_keyboard_stop(qapp) -> None:
    """The noborderfocus rule: a pane is chrome, never a stop."""

    from PySide6.QtCore import Qt

    del qapp
    window = MainWindow()

    for pane in (window.views, window.reader_panel, window.shelf_view):
        assert pane.focusPolicy() == Qt.FocusPolicy.NoFocus, pane
    assert window.shelf_view.empty_panel.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_the_shelf_controls_join_the_ring_only_while_the_shelf_shows(qapp) -> None:
    """FR-BS-059: the shelf joins the existing ring; a hidden page does not."""

    from PySide6.QtCore import Qt

    window = MainWindow()
    window.show()
    qapp.processEvents()

    def stops_after(widget, count):
        seen = []
        nxt = widget.nextInFocusChain()
        while len(seen) < count:
            if (
                nxt.focusPolicy() & Qt.FocusPolicy.TabFocus
                and nxt.isEnabled()
                and nxt.isVisible()
            ):
                seen.append(nxt)
            nxt = nxt.nextInFocusChain()
        return seen

    reader_page_stops = stops_after(window.reader, 1)
    assert window.shelf_view.btn_choose_root not in reader_page_stops

    window.show_shelf_view()
    qapp.processEvents()
    shelf_page_stops = stops_after(window.reader, 1)
    assert shelf_page_stops[0] is window.shelf_view.btn_choose_root
    window.close()


def test_the_shelf_artwork_is_the_bookshelf_picture(qapp) -> None:
    del qapp

    assert Artwork.BOOKSHELF.value == "bookshelf"


# The view's three states -----------------------------------------------------


def test_no_root_states_that_none_was_chosen_and_offers_the_control(qapp) -> None:
    """FR-BS-057."""

    del qapp
    view = ShelfView()

    view.show_no_root()

    assert view.lbl_state.text() == shelf_view_module.NO_ROOT_TEXT
    assert view.btn_choose_root.isEnabled()
    assert not view.btn_rescan.isEnabled()
    assert view.empty_panel.isVisibleTo(view)


def test_no_books_names_the_formats_it_looks_for(qapp) -> None:
    """FR-BS-058: the extensions come from the one declaration of a book."""

    del qapp
    view = ShelfView()

    view.show_no_books()

    assert view.lbl_state.text() == shelf_view_module.NO_BOOKS_TEXT
    for suffix in formats.RECOGNISED:
        assert suffix in view.lbl_hint.text()


def test_a_scan_shuts_both_controls_while_it_runs(qapp) -> None:
    del qapp
    view = ShelfView()

    view.show_scanning()

    assert not view.btn_choose_root.isEnabled()
    assert not view.btn_rescan.isEnabled()


def test_a_finished_scan_reopens_the_controls(qapp) -> None:
    """A scan that ends must never leave the reader with dead controls."""

    del qapp
    view = ShelfView()
    view.show_scanning()

    view.show_count(2)

    assert view.btn_choose_root.isEnabled()
    assert view.btn_rescan.isEnabled()


def test_a_problem_reopens_the_controls_too(qapp) -> None:
    del qapp
    view = ShelfView()
    view.show_scanning()

    view.show_problem("Something went wrong", "Try again")

    assert view.btn_choose_root.isEnabled()
    assert view.btn_rescan.isEnabled()
    assert view.lbl_state.text() == "Something went wrong"


def test_one_work_is_not_called_works(qapp) -> None:
    del qapp
    view = ShelfView()

    view.show_count(1)

    assert view.lbl_count.text() == "1 work"
    assert not view.empty_panel.isVisibleTo(view)


# What the controller tells it ------------------------------------------------


def test_a_build_with_no_shelf_says_no_folder_has_been_chosen(qapp) -> None:
    """A missing collaborator is an answer the reader can act on, not a crash."""

    del qapp
    window = MainWindow()
    controller = _FakeController(window, library=None)

    refresh_shelf(controller)

    assert window.shelf_view.lbl_state.text() == shelf_view_module.NO_ROOT_TEXT


def test_a_watched_root_holding_nothing_reads_as_no_books(qapp) -> None:
    del qapp
    window = MainWindow()
    controller = _FakeController(window, _FakeLibrary(roots=(Path("H:/Books"),)))

    refresh_shelf(controller)

    assert window.shelf_view.lbl_state.text() == shelf_view_module.NO_BOOKS_TEXT


def test_works_on_the_shelf_are_counted(qapp) -> None:
    del qapp
    window = MainWindow()
    library = _FakeLibrary(roots=(Path("H:/Books"),), works=(object(), object()))
    controller = _FakeController(window, library)

    refresh_shelf(controller)

    assert window.shelf_view.lbl_count.text() == "2 works"


def test_the_control_toggles_back_to_the_reader(qapp) -> None:
    del qapp
    window = MainWindow()
    controller = _FakeController(window, _FakeLibrary())

    toggle_shelf(controller)
    assert window.showing_shelf()

    toggle_shelf(controller)
    assert not window.showing_shelf()
