"""UiController wiring: Sections (Structural Bookmarks) dialog."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.structural_bookmarks_dialog import (
    StructuralBookmarkListItem,
    StructuralBookmarksDialog,
    StructuralBookmarksDialogActions,
)


def open_structural_bookmarks_dialog(controller) -> None:
    log = getattr(controller, "_log", logging.getLogger(__name__))

    book_id = None
    try:
        book_id = controller.narration_service.loaded_book_id()
    except Exception:
        book_id = None

    if not book_id:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Sections")
        box.setText("Load a book to view sections.")
        box.open()
        return

    # Pull text directly from the already-loaded book.
    book = None
    normalized_text = ""
    book_title = None
    try:
        book = getattr(controller.narration_service, "_book", None)  # noqa: SLF001
        normalized_text = str(getattr(book, "normalized_text", ""))
        book_title = getattr(book, "title", None)
    except Exception:
        normalized_text = ""
        book_title = None

    svc = getattr(controller, "structural_bookmark_service", None)
    if svc is None:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Sections")
        box.setText("Sections are not available.")
        box.open()
        return

    # Use any already-computed chapter metadata as candidates.
    try:
        chapter_candidates = list(getattr(controller, "_chapters", []) or [])  # noqa: SLF001
    except Exception:
        chapter_candidates = []

    # If chunks are available, allow optional chunk_index resolution.
    try:
        chunks = list(getattr(controller.narration_service, "_chunks", []) or [])  # noqa: SLF001
    except Exception:
        chunks = None

    bookmarks = []
    try:
        bookmarks = list(
            svc.build_for_loaded_book(
                book_id=str(book_id),
                normalized_text=normalized_text,
                chapter_candidates=chapter_candidates,
                chunks=chunks,
            )
        )
    except Exception:
        try:
            log.exception("Sections: build failed")
        except Exception:
            pass
        bookmarks = []

    if not bookmarks:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Sections")
        box.setText("No obvious sections found.")
        box.open()
        return

    def _list_items() -> list[StructuralBookmarkListItem]:
        out: list[StructuralBookmarkListItem] = []
        for b in bookmarks:
            out.append(
                StructuralBookmarkListItem(
                    label=b.label,
                    char_offset=b.char_offset,
                    chunk_index=b.chunk_index,
                    kind=b.kind,
                    level=b.level,
                )
            )
        return out

    def _go_to(it: StructuralBookmarkListItem) -> None:
        voice = controller._selected_voice()  # noqa: SLF001
        if voice is None:
            return

        try:
            controller._last_prepared_voice_id = voice.name  # noqa: SLF001
        except Exception:
            pass

        # Simple semantics: stop immediately without persisting resume; then restart.
        try:
            controller.narration_service.stop(persist_resume=False)
        except Exception:
            pass

        if it.char_offset is not None:
            controller.narration_service.prepare(
                voice=voice,
                start_char_offset=int(it.char_offset),
                force_start_char=int(it.char_offset),
                skip_essay_index=False,
                persist_resume=False,
            )
        else:
            if it.chunk_index is None:
                return
            controller.narration_service.prepare(
                voice=voice,
                start_playback_index=int(it.chunk_index),
            )

        controller.narration_service.start()

        try:
            if getattr(controller, "_sections_dialog", None) is not None:  # noqa: SLF001
                controller._sections_dialog.close()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass

    actions = StructuralBookmarksDialogActions(list_items=_list_items, go_to=_go_to)

    # Ensure only one dialog instance.
    try:
        if getattr(controller, "_sections_dialog", None) is not None:  # noqa: SLF001
            controller._sections_dialog.close()  # noqa: SLF001
    except Exception:
        pass

    controller._sections_dialog = StructuralBookmarksDialog(  # noqa: SLF001
        parent=controller.window,
        actions=actions,
        book_title=book_title,
    )
    controller._sections_dialog.open()  # noqa: SLF001

