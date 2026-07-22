"""Remove the current book from NarrateX's memory, never from disk.

The ❌ control forgets everything the app derived from the loaded book:
bookmarks and the resume position, the persisted ideas map, the cached
narration audio and the last-book auto-load preference. The book file
itself is untouched, so selecting it again later starts completely fresh.

Removal is destructive, so it always passes through a modal confirmation
naming the book and exactly what is deleted, with Cancel as the default.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from voice_reader.ui._ui_controller_book_loading import prepare_for_book_switch


def _in_tests() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _book_title(controller) -> str:
    try:
        book = controller.narration_service.loaded_book()
        title = getattr(book, "title", None)
    except Exception:
        title = None
    return str(title) if title else "this book"


def _confirm_removal(controller) -> bool:
    """Modal confirmation naming the target and the consequence."""

    box = QMessageBox(controller.window)
    box.setWindowTitle("Remove Book")
    box.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    box.setText(
        f"Remove '{_book_title(controller)}' from NarrateX?\n\n"
        "Bookmarks, the resume position, the ideas map and cached narration "
        "audio for this book will be deleted.\n\n"
        "The book file on disk is not touched."
    )
    remove_button = box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    if _in_tests():
        # A modal exec would hang the suite; tests drive the outcome via the
        # explicit `confirmed` parameter instead.
        return False
    box.exec()  # pragma: no cover (modal; exercised interactively)
    return box.clickedButton() is remove_button  # pragma: no cover


def _reset_ui_to_no_book(controller) -> None:
    """Put the window back to its fresh, nothing-loaded state."""

    window = controller.window
    controller._chapters = []  # noqa: SLF001
    controller._current_chapter = None  # noqa: SLF001

    # One block: a window fake missing any of these simply skips the rest;
    # the real MainWindow carries them all.
    try:
        window.set_reader_text("")
        window.set_cover_image(None)
        window.chapter_spine.set_chapters([])
        window.chapter_spine.set_current_chapter(None)
        window.chapter_spine.set_playhead_char_offset(None)
        window.set_chapter_controls_enabled(previous=False, next_=False)
        window.lbl_status.setText("Idle")
        window.progress.setRange(0, 100)
        window.progress.setValue(0)
        window.lbl_progress.setText("0/0")
    except Exception:
        pass

    # The picker (and the ❌ itself) lock again behind the next book, and a
    # still-flashing choose-a-voice prompt has nothing left to ask about.
    attention = getattr(controller, "_picker_attention", None)
    if attention is not None:
        try:
            attention.clear()
        except Exception:
            pass
    try:
        from voice_reader.ui._ui_controller_voices import apply_picker_availability

        apply_picker_availability(controller)
    except Exception:
        pass


def remove_current_book(controller, *, confirmed: bool | None = None) -> None:
    """Forget the loaded book after confirmation; the file stays on disk."""

    try:
        book_id = controller.narration_service.loaded_book_id()
    except Exception:
        book_id = None
    if not book_id:
        return

    if confirmed is None:
        confirmed = _confirm_removal(controller)
    if not confirmed:
        return

    # Cancel per-book background work (ideas indexing, pre-synthesis) first
    # so nothing recreates state mid-removal.
    prepare_for_book_switch(controller)

    forget = getattr(controller.narration_service, "forget_current_book", None)
    if callable(forget):
        try:
            forget()
        except Exception:
            pass

    idea_map = getattr(controller, "idea_map_service", None)
    if idea_map is not None:
        try:
            idea_map.delete_index(book_id=str(book_id))
        except Exception:
            pass

    _reset_ui_to_no_book(controller)
