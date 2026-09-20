"""The shelf filling while the scan is still walking (FR-BS-036).

The scanner is faked, because a real walk cannot be asked to settle a chosen
number of entries on demand; everything downstream of it is real: the library
does the folding, the view is a real `ShelfView` and the grid is a real
`ShelfGrid`, so what these tests read off the count label and the grid is what
a reader would see.

The marshal is driven by hand rather than by an event loop, exactly as
`test_shelf_scan_worker.py` drives it, which is what lets a test say the worker
itself touched no widget.
"""

from __future__ import annotations

import threading
from pathlib import Path

from voice_reader.application.services.shelf import ShelfLibrary
from voice_reader.application.services.shelf.filling import ENTRIES_BETWEEN_DRAWS
from voice_reader.application.services.shelf.scanning import ScanReport
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.ui import _ui_controller_shelf_scan as scan_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid
from voice_reader.ui.shelf_view import SCANNING_TEXT

from tests.application.shelf.shelf_fakes import FakeBookmarks, FakeIndex, key

ROOT = Path("H:/Books")


def entry(number: int, *, subjects: tuple[str, ...] = ()) -> ShelfEntry:
    return ShelfEntry(
        key=key(f"H:/Books/{number}.mobi"),
        title=f"Book {number}",
        author=f"Author {number}",
        subjects=subjects,
    )


class _Covers:
    def held_for(self, work) -> bytes | None:
        del work
        return None

    def thumbnail(self, work) -> bytes | None:
        del work
        return None


class _FakeScanner:
    """Settles a prepared run of entries, then answers a report."""

    def __init__(self, entries: tuple[ShelfEntry, ...]) -> None:
        self._entries = entries
        self.ran_on: str | None = None

    def scan(self, *, on_entry=None, **kwargs):
        del kwargs
        self.ran_on = threading.current_thread().name
        for settled in self._entries:
            if on_entry is not None:
                on_entry(settled)
        return ScanReport(found=len(self._entries), added=len(self._entries))


class _Shelf:
    def __init__(self, library, scanner) -> None:
        self.library = library
        self.scanner = scanner
        self.covers = _Covers()
        self.thumbnails = None


class _Log:
    def exception(self, *args, **kwargs) -> None:  # pragma: no cover (unused here)
        del args, kwargs


class _Controller:
    """What the scan helpers reach for, with the marshal driven by hand."""

    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._log = _Log()
        self._shelf_scan_thread: threading.Thread | None = None
        self.posted: list = []

        class _Signal:
            def __init__(self, posted) -> None:
                self._posted = posted

            def emit(self, fn) -> None:
                self._posted.append(fn)

        self.ui_call_requested = _Signal(self.posted)

    def run_posted(self, *, count: int | None = None) -> None:
        """Run what the worker handed back; the first `count` of it if asked."""

        taken = self.posted if count is None else self.posted[:count]
        for fn in list(taken):
            fn()
        del self.posted[: len(list(taken))]


def _shelf(entries: tuple[ShelfEntry, ...], *, stated=None):
    index = FakeIndex(roots=(ROOT,), stated=stated or {})
    library = ShelfLibrary(index=index, bookmarks=FakeBookmarks())
    return _Shelf(library, _FakeScanner(entries)), index


def _controller(entries, *, stated=None, with_grid: bool = True):
    shelf, index = _shelf(entries, stated=stated)
    window = MainWindow()
    controller = _Controller(window, shelf)
    if with_grid:
        grid = ShelfGrid(covers=shelf.covers, parent=window.shelf_view)
        window.shelf_view.install_grid(grid)
    return controller, index


def _walk(controller) -> None:
    """Start the scan and wait for the worker, leaving the posts unrun."""

    scan_helpers.rescan_shelf(controller)
    thread = controller._shelf_scan_thread  # noqa: SLF001
    assert thread is not None
    thread.join(timeout=5.0)
    assert not thread.is_alive(), "the scan worker did not finish"


def test_the_shelf_holds_works_before_the_scan_ends(qapp) -> None:
    """The acceptance in FR-BS-036, read off a real grid."""

    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))

    _walk(controller)
    # Everything but the last post, which is the finished report.
    controller.run_posted(count=len(controller.posted) - 1)

    grid = controller.window.shelf_view.grid
    assert len(grid.works()) == ENTRIES_BETWEEN_DRAWS
    assert grid.isVisibleTo(controller.window.shelf_view)
    grid.release()


def test_the_worker_touches_no_widget_itself(qapp) -> None:
    """Nothing is drawn until the posts are run on this thread."""

    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))

    _walk(controller)

    view = controller.window.shelf_view
    assert view.empty_panel.isVisibleTo(view)
    assert view.lbl_state.text() == SCANNING_TEXT
    assert not view.grid.works()
    view.grid.release()


def test_a_filling_shelf_counts_what_it_has_so_far(qapp) -> None:
    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))

    _walk(controller)
    controller.run_posted(count=len(controller.posted) - 1)

    shown = f"{ENTRIES_BETWEEN_DRAWS} works so far"
    assert controller.window.shelf_view.lbl_count.text() == shown
    controller.window.shelf_view.grid.release()


def test_the_scan_controls_stay_shut_while_it_fills(qapp) -> None:
    """A second scan would fight the first; a filter would narrow an arrival."""

    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))

    _walk(controller)
    controller.run_posted(count=len(controller.posted) - 1)

    view = controller.window.shelf_view
    assert not view.btn_rescan.isEnabled()
    assert not view.btn_choose_root.isEnabled()
    assert not view.btn_filter.isEnabled()
    view.grid.release()


def test_a_walk_too_short_to_fill_draws_nothing_early(qapp) -> None:
    """Under one batch, the words about reading the folders stay where they are."""

    del qapp
    short = tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS - 1))
    controller, _ = _controller(short)

    _walk(controller)

    view = controller.window.shelf_view
    assert len(controller.posted) == 1
    assert view.empty_panel.isVisibleTo(view)
    assert view.lbl_state.text() == SCANNING_TEXT
    view.grid.release()


def test_the_filter_still_narrows_a_filling_shelf(qapp) -> None:
    """FR-BS-042 is not suspended by a rescan."""

    del qapp
    horror = tuple(
        entry(n, subjects=("Horror",)) for n in range(ENTRIES_BETWEEN_DRAWS - 1)
    )
    controller, _ = _controller(horror + (entry(ENTRIES_BETWEEN_DRAWS),))
    controller._shelf_query = ShelfQuery(genres=("Horror",))  # noqa: SLF001

    _walk(controller)
    controller.run_posted(count=len(controller.posted) - 1)

    grid = controller.window.shelf_view.grid
    assert len(grid.works()) == ENTRIES_BETWEEN_DRAWS - 1
    grid.release()


def test_a_batch_the_filter_empties_leaves_the_words_alone(qapp) -> None:
    """A filter admitting none of what has arrived is not an empty shelf.

    The grid would otherwise take the place of the words and stand there with
    nothing in it, which reads as a library that holds nothing.
    """

    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))
    controller._shelf_query = ShelfQuery(genres=("Horror",))  # noqa: SLF001

    _walk(controller)
    controller.run_posted(count=len(controller.posted) - 1)

    view = controller.window.shelf_view
    assert view.empty_panel.isVisibleTo(view)
    assert view.lbl_state.text() == SCANNING_TEXT
    assert not view.grid.works()
    view.grid.release()


def test_a_shelf_that_went_away_mid_walk_draws_nothing(qapp) -> None:
    """The batch is already in flight when the library goes; it is not a fault."""

    del qapp
    controller, _ = _controller(tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)))

    _walk(controller)
    controller.shelf = None
    controller.run_posted(count=len(controller.posted) - 1)

    view = controller.window.shelf_view
    assert view.empty_panel.isVisibleTo(view)
    assert not view.grid.works()
    view.grid.release()


def test_a_view_with_no_grid_still_fills_its_count(qapp) -> None:
    """A build whose grid was never installed says the number rather than raising."""

    del qapp
    controller, _ = _controller(
        tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS)), with_grid=False
    )

    _walk(controller)
    controller.run_posted(count=len(controller.posted) - 1)

    shown = f"{ENTRIES_BETWEEN_DRAWS} works so far"
    assert controller.window.shelf_view.lbl_count.text() == shown


def test_the_settled_shelf_replaces_the_filling_one(qapp) -> None:
    """The last post is the report, which redraws from the saved index."""

    del qapp
    controller, index = _controller(
        tuple(entry(n) for n in range(ENTRIES_BETWEEN_DRAWS))
    )
    index.save_entries(tuple(entry(n) for n in range(3)))

    _walk(controller)
    controller.run_posted()

    view = controller.window.shelf_view
    assert view.lbl_count.text() == "3 works"
    assert view.btn_rescan.isEnabled()
    view.grid.release()
