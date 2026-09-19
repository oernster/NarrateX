"""Leaving nothing running when the window closes.

NarrationService owns resume persistence, so nothing here touches it. What is
left is the Ideas indexing worker, which runs in a process of its own: a run
that ends without cancelling it leaves that process alive after the window has
gone, which the reader reads as the application refusing to quit.

Every step is best effort and independent of the others, because a shutdown
that raises has failed at the one job it had.
"""

from __future__ import annotations


def close_sections_dialog(controller) -> None:
    """The Sections dialog owns no background work; only close it."""

    try:
        dialog = getattr(controller, "_sections_dialog", None)  # noqa: SLF001
        if dialog is not None:
            dialog.close()
    except Exception:
        pass


def cancel_ideas_launch(controller) -> None:
    """Stop any in-flight launcher orchestration."""

    try:
        if controller._ideas_launch_cancel is not None:  # noqa: SLF001
            controller._ideas_launch_cancel.set()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass


def cancel_ideas_indexing(controller) -> None:
    """Cancel the indexing job and stop the timer watching it."""

    book_id = getattr(controller, "_ideas_index_job_book_id", None)
    if not book_id:
        return
    manager = getattr(controller, "idea_indexing_manager", None)
    if manager is not None:
        try:
            manager.cancel(book_id=str(book_id))
        except Exception:  # pragma: no cover
            pass
    controller._ideas_index_job_book_id = None  # noqa: SLF001
    try:
        if controller._ideas_index_timer is not None:  # noqa: SLF001
            controller._ideas_index_timer.stop()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass


def on_app_exit(controller) -> None:
    """Best-effort cleanup for background tasks, in order."""

    close_sections_dialog(controller)
    cancel_ideas_launch(controller)
    cancel_ideas_indexing(controller)


def run_ui_callable(fn: object) -> None:
    """Execute a callable on the Qt UI thread, swallowing whatever it raises."""

    try:
        if callable(fn):
            fn()
    except Exception:
        return
