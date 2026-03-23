"""UiController wiring: Sections (Structural Bookmarks) dialog."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.structural_bookmarks_dialog import (
    StructuralBookmarkListItem,
    StructuralBookmarksDialog,
    StructuralBookmarksDialogActions,
)

from voice_reader.ui.structural_bookmarks_helpers import compute_structural_bookmarks


def open_structural_bookmarks_dialog(controller) -> None:
    log = getattr(controller, "_log", logging.getLogger(__name__))

    comp = compute_structural_bookmarks(controller, log=log)
    if comp is None:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Sections")
        box.setText("Load a book to view sections.")
        box.open()
        return

    if not comp.bookmarks:
        box = QMessageBox(controller.window)
        box.setWindowTitle("Sections")
        box.setText("No obvious sections found.")
        box.open()
        return

    def _list_items() -> list[StructuralBookmarkListItem]:
        out: list[StructuralBookmarkListItem] = []
        for b in comp.bookmarks:
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
            # Sections are reading-navigation: keep the same safety semantics as
            # normal narration start detection.
            target = int(it.char_offset)
            boundary = comp.min_char_offset
            force = target
            if boundary is not None and target < int(boundary):
                # Defensive guard: never force narration into front matter.
                # If this regresses, the structural bookmark service should have
                # prevented it, but this guard avoids user-facing breakage.
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
            if (
                getattr(controller, "_sections_dialog", None) is not None
            ):  # noqa: SLF001
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
        book_title=comp.book_title,
    )
    controller._sections_dialog.open()  # noqa: SLF001
