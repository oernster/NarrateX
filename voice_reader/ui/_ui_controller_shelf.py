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

from PySide6.QtWidgets import QFileDialog

CHOOSE_ROOT_TITLE = "Choose the folder holding your books"

SCAN_FAILED_TEXT = "Your folders could not be read"
SCAN_FAILED_HINT = "See the log for what went wrong, then try again."


def toggle_shelf(controller) -> None:
    """Show the shelf; go back to the reader when it is already showing."""

    window = controller.window
    if window.showing_shelf():
        window.show_reader_view()
        return
    refresh_shelf(controller)
    window.show_shelf_view()


def refresh_shelf(controller) -> None:
    """Tell the view which of its three states it is in.

    The counts come from the library, so a shelf reopened after a scan says
    what the index now holds without the view keeping a copy of it.
    """

    view = controller.window.shelf_view
    library = controller.shelf.library if controller.shelf is not None else None
    if library is None or not library.roots():
        view.show_no_root()
        return
    works = library.works()
    if not works:
        view.show_no_books()
        return
    view.show_count(len(works))


def choose_shelf_root(controller) -> None:
    """Nominate a folder, then say what the shelf looks like with it.

    A folder already covered by a watched root is refused by the library
    (FR-BS-001c); the reader is told which root already covers it rather than
    being left with a control that appeared to do nothing.
    """

    if controller.shelf is None:
        return
    chosen = QFileDialog.getExistingDirectory(controller.window, CHOOSE_ROOT_TITLE)
    if not chosen:
        return
    outcome = controller.shelf.library.add_root(Path(chosen))
    if not outcome.added and outcome.covered_by is not None:
        controller.window.lbl_status.setText(
            f"That folder is already covered by {outcome.covered_by}"
        )
        return
    rescan_shelf(controller)


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
