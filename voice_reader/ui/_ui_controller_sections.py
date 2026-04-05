"""UiController wiring: Sections (Structural Bookmarks) dialog."""

from __future__ import annotations

import logging
import threading

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.structural_bookmarks_dialog import (
    StructuralBookmarkListItem,
    StructuralBookmarksDialog,
    StructuralBookmarksDialogActions,
)

from voice_reader.ui.structural_bookmarks_helpers import compute_structural_bookmarks


def open_structural_bookmarks_dialog(controller) -> None:
    log = getattr(controller, "_log", logging.getLogger(__name__))

    # Preserve existing UX: if no book is loaded, show a lightweight message box.
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

    # Ensure only one dialog instance.
    try:
        if getattr(controller, "_sections_dialog", None) is not None:  # noqa: SLF001
            controller._sections_dialog.close()  # noqa: SLF001
    except Exception:
        pass

    # Create dialog immediately with a loading state.
    # Book title is best-effort; avoid any heavy computation on the UI thread.
    try:
        book = getattr(controller.narration_service, "_book", None)  # noqa: SLF001
        book_title = getattr(book, "title", None)
    except Exception:
        book_title = None

    items: list[StructuralBookmarkListItem] = []
    dlg = StructuralBookmarksDialog(
        parent=controller.window,
        actions=StructuralBookmarksDialogActions(
            list_items=lambda: items,
            go_to=lambda it: _go_to(controller, it),
        ),
        book_title=book_title,
    )
    controller._sections_dialog = dlg  # noqa: SLF001
    dlg.set_loading(message="Loading sections…")
    dlg.open()

    # Launch computation off the UI thread.
    token = object()
    controller._sections_compute_token = token  # noqa: SLF001

    def _on_destroyed(_obj=None) -> None:
        # Invalidate the pending compute so the UI won't be updated after close.
        try:
            if getattr(controller, "_sections_compute_token", None) is token:  # noqa: SLF001
                controller._sections_compute_token = None  # noqa: SLF001
        except Exception:
            return

    try:
        dlg.destroyed.connect(_on_destroyed)
    except Exception:
        pass

    def _post_to_ui(fn) -> None:
        try:
            controller.ui_call_requested.emit(fn)
            return
        except Exception:
            pass
        try:
            fn()
        except Exception:
            return

    def _worker() -> None:
        comp = compute_structural_bookmarks(controller, log=log)

        def _apply() -> None:
            # Cancel if user closed/re-opened the dialog or a new job started.
            if getattr(controller, "_sections_compute_token", None) is not token:  # noqa: SLF001
                return
            cur = getattr(controller, "_sections_dialog", None)  # noqa: SLF001
            if cur is None or cur is not dlg:
                return

            if comp is None:
                dlg.set_empty(message="Load a book to view sections.")
                return
            if not getattr(comp, "bookmarks", None):
                dlg.set_empty(message="No obvious sections found.")
                return

            nonlocal items
            items = [
                StructuralBookmarkListItem(
                    label=b.label,
                    char_offset=b.char_offset,
                    chunk_index=b.chunk_index,
                    kind=b.kind,
                    level=b.level,
                )
                for b in comp.bookmarks
            ]
            dlg.set_items(items=items)

        _post_to_ui(_apply)

    t = threading.Thread(target=_worker, name="SectionsCompute", daemon=True)
    try:
        controller._sections_compute_thread = t  # noqa: SLF001
    except Exception:
        pass
    t.start()


def _go_to(controller, it: StructuralBookmarkListItem) -> None:
    # Re-compute the boundary at click time (cheap vs. full section scan), so we
    # preserve the existing safety semantics.
    comp = compute_structural_bookmarks(controller)
    boundary = getattr(comp, "min_char_offset", None) if comp is not None else None

    voice = controller._selected_voice()  # noqa: SLF001
    if voice is None:
        return

    try:
        controller._last_prepared_voice_id = voice.name  # noqa: SLF001
    except Exception:
        pass

    try:
        controller.narration_service.stop(persist_resume=False)
    except Exception:
        pass

    if it.char_offset is not None:
        target = int(it.char_offset)
        force = target
        if boundary is not None and target < int(boundary):
            target = int(boundary)
            force = None

        controller.narration_service.prepare(
            voice=voice,
            start_char_offset=int(target),
            force_start_char=None if force is None else int(force),
            skip_essay_index=True,
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
        dlg = getattr(controller, "_sections_dialog", None)  # noqa: SLF001
        if dlg is not None:
            dlg.close()
    except Exception:  # pragma: no cover
        pass
