"""The view with a grid in it; the controller's own shelf entry points.

The earlier shelf tests drive the helper functions directly. These go through the
methods a signal actually reaches, because a mixin that is never called through
the controller is a wiring claim nobody has checked.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.progress import UNREAD
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid
from voice_reader.ui.shelf_view import ShelfView


def _work(title: str = "Dune", author: str = "Frank Herbert") -> Work:
    key = ShelfKey(path=Path("H:/Books") / f"{title}.epub", size_bytes=1, modified_ns=1)
    return Work(
        title=title,
        author=author,
        entries=(ShelfEntry(key=key, title=title, author=author),),
    )


class _Covers:
    def held_for(self, work: Work) -> bytes | None:
        del work
        return None

    def thumbnail(self, work: Work) -> bytes | None:
        del work
        return None


class _Library:
    def __init__(self, roots=(), works=()) -> None:
        self._roots = tuple(roots)
        self._works = tuple(works)

    def roots(self):
        return self._roots

    def works(self):
        return self._works

    def view_of(self, works, query):
        """This stand-in narrows nothing; the tests using it are not about that."""

        del query
        return tuple(works)

    def progress_of(self, work: Work):
        del work
        return UNREAD


class _Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.covers = _Covers()
        self.scanner = None
        self.thumbnails = None


class _Controller:
    """Carries what the shelf mixin reaches for; records what it opened."""

    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None
        self.opened: list[Work] = []

    # The mixin's methods, taken from the real class so this is not a copy.
    from voice_reader.ui._ui_controller_shelf_api import ShelfApi

    install_shelf_grid = ShelfApi.install_shelf_grid
    refresh_shelf = ShelfApi.refresh_shelf
    tag_work = ShelfApi.tag_work
    toggle_shelf = ShelfApi.toggle_shelf
    open_work = ShelfApi.open_work


# The view with a grid ----------------------------------------------------


def test_an_installed_grid_is_hidden_until_there_are_works(qapp) -> None:
    del qapp
    view = ShelfView()
    grid = ShelfGrid(covers=_Covers(), parent=view)

    view.install_grid(grid)

    assert view.grid is grid
    assert not grid.isVisibleTo(view)
    grid.release()


def test_works_show_the_grid_and_hide_the_empty_block(qapp) -> None:
    del qapp
    view = ShelfView()
    grid = ShelfGrid(covers=_Covers(), parent=view)
    view.install_grid(grid)

    view.show_works((_work("Dune"), _work("Emma")))

    assert grid.isVisibleTo(view)
    assert not view.empty_panel.isVisibleTo(view)
    assert len(grid.works()) == 2
    grid.release()


def test_an_empty_state_hides_the_grid_again(qapp) -> None:
    del qapp
    view = ShelfView()
    grid = ShelfGrid(covers=_Covers(), parent=view)
    view.install_grid(grid)
    view.show_works((_work(),))

    view.show_no_root()

    assert not grid.isVisibleTo(view)
    assert view.empty_panel.isVisibleTo(view)
    grid.release()


def test_the_grid_joins_the_ring_once_installed(qapp) -> None:
    """FR-BS-059: the works are reachable from the keyboard."""

    del qapp
    view = ShelfView()

    # Choose a folder, Rescan, Filter, the search field, the ordering and the
    # layout, before the works arrive.
    assert len(view.ring_stops()) == 6
    assert view.ring_stops()[-1] is view.btn_layout

    grid = ShelfGrid(covers=_Covers(), parent=view)
    view.install_grid(grid)

    assert view.ring_stops()[-1] is grid
    assert grid.nextInFocusChain() is not None
    grid.release()


# Through the controller --------------------------------------------------


def test_the_controller_installs_a_grid_carrying_the_cover_service(qapp) -> None:
    del qapp
    window = MainWindow()
    shelf = _Shelf(_Library(roots=(Path("H:/Books"),), works=(_work(),)))
    controller = _Controller(window, shelf)

    controller.install_shelf_grid()

    assert window.shelf_view.grid is not None
    window.shelf_view.grid.release()


def test_installing_twice_keeps_the_first_grid(qapp) -> None:
    del qapp
    window = MainWindow()
    controller = _Controller(window, _Shelf(_Library()))
    controller.install_shelf_grid()
    first = window.shelf_view.grid

    controller.install_shelf_grid()

    assert window.shelf_view.grid is first
    first.release()


def test_no_shelf_means_no_grid(qapp) -> None:
    del qapp
    window = MainWindow()

    _Controller(window, None).install_shelf_grid()

    assert window.shelf_view.grid is None


class _RecordingController(_Controller):
    """Records what it was asked to open instead of loading a book.

    The connection is made when the grid is installed, so the recording has to
    exist before that: reassigning the attribute afterwards would leave the grid
    still holding the method it was given.
    """

    def open_work(self, work) -> None:
        self.opened.append(work)


def test_opening_a_tile_reaches_the_controller(qapp) -> None:
    """The grid's signal is connected to the controller, not merely emitted."""

    del qapp
    window = MainWindow()
    work = _work()
    shelf = _Shelf(_Library(roots=(Path("H:/Books"),), works=(work,)))
    controller = _RecordingController(window, shelf)
    controller.install_shelf_grid()
    grid = window.shelf_view.grid
    grid.show_works((work,))

    grid.clicked.emit(grid.model().index(0, 0))

    assert controller.opened == [work]
    grid.release()


def test_the_controller_draws_the_works_on_the_grid(qapp) -> None:
    del qapp
    window = MainWindow()
    works = (_work("Dune"), _work("Emma"))
    controller = _Controller(
        window, _Shelf(_Library(roots=(Path("H:/Books"),), works=works))
    )
    controller.install_shelf_grid()

    controller.refresh_shelf()

    assert len(window.shelf_view.grid.works()) == 2
    assert window.shelf_view.lbl_count.text() == "2 works"
    window.shelf_view.grid.release()


def test_the_control_shows_and_hides_the_shelf_through_the_controller(qapp) -> None:
    del qapp
    window = MainWindow()
    controller = _Controller(window, _Shelf(_Library()))

    controller.toggle_shelf()
    assert window.showing_shelf()

    controller.toggle_shelf()
    assert not window.showing_shelf()


def test_the_grid_is_a_real_stop_and_the_panes_are_not(qapp) -> None:
    del qapp
    window = MainWindow()
    controller = _Controller(window, _Shelf(_Library()))
    controller.install_shelf_grid()

    assert window.shelf_view.grid.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert window.shelf_view.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert window.views.focusPolicy() == Qt.FocusPolicy.NoFocus
    window.shelf_view.grid.release()
