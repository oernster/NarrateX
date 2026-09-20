"""What the shelf control does; what the shelf view is told to show.

Extracted from `ui_controller.py` the way every other controller concern is, so
the entry points stay one function each and the window stays free of the
services.

**The shelf without a library is still a shelf.** A build with no shelf wired
shows the control and says no folder has been chosen, rather than hiding a
control or raising: the reader can act on the first; nobody can act on the
second.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from voice_reader.ui._message_box_utils import _in_tests
from voice_reader.ui._ui_controller_book_loading import (
    load_selected_book,
    narration_holds_the_book,
    prepare_for_book_switch,
)
from voice_reader.ui.shelf_grid import ShelfGrid

CHOOSE_ROOT_TITLE = "Choose the folder holding your books"

# Where the folder dialog opens. Named rather than written into the call; the
# one place to change if a platform ever spells it differently.
DOWNLOADS_FOLDER = "Downloads"

MISSING_TITLE = "Book not found"
MISSING_RESCAN = "Rescan"
MISSING_CLOSE = "Close"

SCAN_FAILED_TEXT = "Your folders could not be read"
SCAN_FAILED_HINT = "See the log for what went wrong, then try again."

# FR-BS-055a. A refusal names what can be done about it, so this says which
# two controls end the narration rather than only that the shelf will not act.
LOCKED_TEXT = "Pause or stop the narration to open another book"


def toggle_shelf(controller) -> None:
    """Show the shelf; go back to the reader when it is already showing."""

    window = controller.window
    if window.showing_shelf():
        window.show_reader_view()
        return
    refresh_shelf(controller)
    window.show_shelf_view()


def install_shelf_grid(controller) -> None:
    """Build the grid and give it to the view, once, at wiring time.

    The grid is built here rather than in the view because it needs the cover
    service and the reading progress, which are the controller's collaborators
    and not the window's.
    """

    view = controller.window.shelf_view
    if view.grid is not None or controller.shelf is None:
        return
    grid = ShelfGrid(
        covers=controller.shelf.covers,
        progress_of=controller.shelf.library.progress_of,
        parent=view,
    )
    grid.work_activated.connect(controller.open_work)
    view.install_grid(grid)


def refresh_shelf(controller) -> None:
    """Tell the view which of its states it is in, then what to draw.

    The works come from the library, so a shelf reopened after a scan draws what
    the index now holds without the view keeping a copy of it.
    """

    view = controller.window.shelf_view
    apply_shelf_lock(controller)
    library = controller.shelf.library if controller.shelf is not None else None
    if library is None or not library.roots():
        view.show_no_root()
        return
    works = library.works()
    if not works:
        view.show_no_books()
        return
    view.show_works(works)


def apply_shelf_lock(controller, *, locked: bool | None = None) -> None:
    """Tell the grid whether a book can be opened, so its rings read true.

    The state stream calls this on every change; the shelf calls it on its way
    open, because a shelf shown between two state updates would otherwise draw
    itself green over a book that is being read aloud.
    """

    view = getattr(controller.window, "shelf_view", None)
    grid = getattr(view, "grid", None)
    if grid is None:
        return
    held = narration_holds_the_book(controller) if locked is None else locked
    grid.set_locked(held)


def choose_shelf_root(controller) -> None:
    """Nominate a folder, then say what the shelf looks like with it.

    A folder already covered by a watched root is refused by the library
    (FR-BS-001c); the reader is told which root already covers it rather than
    being left with a control that appeared to do nothing.
    """

    if controller.shelf is None:
        return
    chosen = QFileDialog.getExistingDirectory(
        controller.window, CHOOSE_ROOT_TITLE, str(_first_folder_to_show())
    )
    if not chosen:
        return
    outcome = controller.shelf.library.add_root(Path(chosen))
    if not outcome.added and outcome.covered_by is not None:
        controller.window.lbl_status.setText(
            f"That folder is already covered by {outcome.covered_by}"
        )
        return
    rescan_shelf(controller)


def _first_folder_to_show() -> Path:
    """Where the folder dialog opens: the reader's downloads, else their home.

    Books arrive in the downloads folder, so that is where the search for them
    starts. A machine without one falls back to the home folder rather than to
    whatever directory the application happened to be started from.
    """

    downloads = Path.home() / DOWNLOADS_FOLDER
    return downloads if downloads.is_dir() else Path.home()


def rescan_shelf(controller) -> None:
    """Walk every watched root on a worker thread, then say what came back.

    The scan reads thousands of files, so it cannot run on the Qt thread. The
    worker touches no widget: it hands the finished report back through
    `ui_call_requested`, which is the one marshal the controller already owns.

    A second scan while one is running is refused rather than queued. Two scans
    over one tree can only race each other to save the same index.
    """

    if controller.shelf is None:
        return
    running = controller._shelf_scan_thread  # noqa: SLF001
    if running is not None and running.is_alive():
        return

    controller.window.shelf_view.show_scanning()
    scanner = controller.shelf.scanner

    def _worker() -> None:
        try:
            report = scanner.scan()
        except Exception as caught:  # noqa: BLE001
            # Deliberately broad. A scan reaches whatever the reader nominated,
            # so it can fail in ways no list of exception types will cover; the
            # one thing that must not happen is a worker dying quietly behind a
            # view that says it is still reading.
            #
            # The failure is bound to its own name and handed in as a default
            # argument: Python unbinds an `except ... as` name when the block
            # ends, so a lambda closing over it reads nothing by the time the Qt
            # thread runs it.
            controller.ui_call_requested.emit(
                lambda failure=caught: _scan_failed(controller, failure)
            )
            return
        controller.ui_call_requested.emit(lambda: _scan_finished(controller, report))

    thread = threading.Thread(target=_worker, name="shelf-scan", daemon=True)
    controller._shelf_scan_thread = thread  # noqa: SLF001
    thread.start()


def _scan_finished(controller, report) -> None:
    """Runs on the Qt thread. Says what the scan found and what it could not."""

    refresh_shelf(controller)
    if report.unreachable_roots:
        named = ", ".join(str(root) for root in report.unreachable_roots)
        controller.window.lbl_status.setText(f"Could not reach {named}")


def _scan_failed(controller, error: Exception) -> None:
    """Runs on the Qt thread. A failure the reader can see and act on."""

    controller._log.exception("Shelf scan failed", exc_info=error)
    controller.window.shelf_view.show_problem(SCAN_FAILED_TEXT, SCAN_FAILED_HINT)


def open_work(controller, work) -> None:
    """Load a work's cheapest format, exactly as the file dialog would.

    FR-BS-055. The reader is put back on the reading view, because a book opened
    with the shelf still covering it would leave them looking at the shelf while
    the words they asked for loaded behind it.

    FR-BS-055a: while the engine is narrating, the refusal happens HERE, before
    anything is undone. The loader further down refuses too; by then this
    function has already cancelled the current book's indexing and its
    pre-synthesis and moved the reader off the shelf, all to arrive at a load
    that never runs.
    """

    if controller.shelf is None:
        return
    if narration_holds_the_book(controller):
        controller.window.lbl_status.setText(LOCKED_TEXT)
        return
    path = controller.shelf.library.path_to_open(work)
    if not path.is_file():
        _missing(controller, path)
        return
    prepare_for_book_switch(controller)
    controller.window.show_reader_view()
    load_selected_book(controller, path=path)


def _missing(controller, path: Path) -> None:
    """FR-BS-056: the file is gone, so name it and offer a rescan."""

    controller.window.lbl_status.setText(f"Not found: {path}")
    box = QMessageBox(controller.window)
    box.setWindowTitle(MISSING_TITLE)
    box.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    box.setText(
        "That book is no longer where the shelf last saw it.\n\n"
        f"{path}\n\n"
        "A rescan will bring the shelf up to date with what is on disk now."
    )
    rescan_button = box.addButton(MISSING_RESCAN, QMessageBox.ButtonRole.AcceptRole)
    close_button = box.addButton(MISSING_CLOSE, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(rescan_button)
    if _in_tests():
        # A modal exec would hang the suite. The two outcomes are driven through
        # `rescan_shelf` and the status line, both tested directly.
        return
    box.exec()  # pragma: no cover (modal; exercised interactively)
    if box.clickedButton() is not close_button:  # pragma: no cover
        rescan_shelf(controller)
