"""Walking the roots off the Qt thread; the shelf filling while it walks.

Split from `_ui_controller_shelf.py` because the scan is the one shelf concern
with a thread in it: everything here is about what runs where and what is safe
to touch from which side, which is a different thing to read than what a
control does.

**Nothing in the worker touches a widget.** The walk hands work back through
`ui_call_requested`, the one marshal the controller already owns; Qt
delivers it on the thread the window lives on. That holds for the finished
report, for a failure and for every batch of entries the shelf is drawn from
while the walk is still going (FR-BS-036).

**Its sibling is imported inside the functions that need it.**
`_ui_controller_shelf` imports the scan from here, because choosing a folder
and a book that has gone missing both ask for one; importing it back at module
level would close the circle. Every one of these calls happens long after
import, so a deferred import costs nothing but the line it is written on.
"""

from __future__ import annotations

import threading

from voice_reader.application.services.shelf.filling import ShelfFilling

SCAN_FAILED_TEXT = "Your folders could not be read"
SCAN_FAILED_HINT = "See the log for what went wrong, then try again."


def rescan_shelf(controller) -> None:
    """Walk every watched root on a worker thread, then say what came back.

    The scan reads thousands of files, so it cannot run on the Qt thread.

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
    filling = ShelfFilling()

    def _settled(entry) -> None:
        """Runs on the worker as each entry lands. Draws when one is due."""

        ready = filling.record(entry)
        if ready is not None:
            controller.ui_call_requested.emit(
                lambda entries=ready: _fill_shelf(controller, entries)
            )

    def _worker() -> None:
        try:
            report = scanner.scan(on_entry=_settled)
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


def _fill_shelf(controller, entries) -> None:
    """Runs on the Qt thread. FR-BS-036: the shelf as far as the walk has got.

    The filter is applied to the batch, because a reader who narrowed their
    shelf then pressed Rescan would read their whole library flashing past as
    the filter having been forgotten.

    A batch with nothing left to show leaves the words about reading the
    folders where they are, since they say more than an empty grid under them
    would. The test is made after the filter rather than before it: a hundred
    books that the filter admits none of is exactly as empty as no books.
    """

    from voice_reader.ui._ui_controller_shelf import apply_shelf_lock, shelf_query

    if controller.shelf is None:
        return
    library = controller.shelf.library
    held = library.works_so_far(entries)
    query = shelf_query(controller)
    shown = library.view_of(held, query) if query.filters_by_genre else held
    if not shown:
        return
    apply_shelf_lock(controller)
    controller.window.shelf_view.show_filling(shown)


def _scan_finished(controller, report) -> None:
    """Runs on the Qt thread. Says what the scan found and what it could not."""

    from voice_reader.ui._ui_controller_shelf import refresh_shelf

    refresh_shelf(controller)
    if report.unreachable_roots:
        named = ", ".join(str(root) for root in report.unreachable_roots)
        controller.window.lbl_status.setText(f"Could not reach {named}")


def _scan_failed(controller, error: Exception) -> None:
    """Runs on the Qt thread. A failure the reader can see and act on."""

    controller._log.exception("Shelf scan failed", exc_info=error)
    controller.window.shelf_view.show_problem(SCAN_FAILED_TEXT, SCAN_FAILED_HINT)
