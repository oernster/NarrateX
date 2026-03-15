"""UiController bookmark dialog wiring."""

from __future__ import annotations

from voice_reader.ui.bookmarks_dialog import BookmarksDialog, BookmarksDialogActions


def open_bookmarks_dialog(controller) -> None:
    book_id = controller.narration_service.loaded_book_id()
    if not book_id:
        return

    def _list() -> list:
        return controller.bookmark_service.list_bookmarks(book_id=book_id)

    def _add() -> None:
        chunk_index, char_offset = controller.narration_service.current_position()
        if chunk_index is None or char_offset is None:
            return
        try:
            existing = controller.bookmark_service.list_bookmarks(book_id=book_id)
        except Exception:
            existing = []
        for bm in existing:
            if int(getattr(bm, "chunk_index", -1)) == int(chunk_index):
                return
        controller.bookmark_service.add_bookmark(
            book_id=book_id,
            char_offset=int(char_offset),
            chunk_index=int(chunk_index),
        )

    def _goto(bm) -> None:
        voice = controller._selected_voice()  # noqa: SLF001
        if voice is None:
            return
        try:
            controller.narration_service.stop()
        except Exception:
            pass
        controller._last_prepared_voice_id = voice.name  # noqa: SLF001
        controller.narration_service.prepare(
            voice=voice,
            start_playback_index=int(getattr(bm, "chunk_index")),
        )
        controller.narration_service.start()
        try:
            if controller._bookmarks_dialog is not None:  # noqa: SLF001
                controller._bookmarks_dialog.close()  # noqa: SLF001
        except Exception:
            pass

    def _delete(bm) -> None:
        controller.bookmark_service.delete_bookmark(
            book_id=book_id,
            bookmark_id=int(getattr(bm, "bookmark_id")),
        )

    actions = BookmarksDialogActions(
        list_bookmarks=_list,
        add_bookmark=_add,
        go_to_bookmark=_goto,
        delete_bookmark=_delete,
    )

    try:
        if controller._bookmarks_dialog is not None:  # noqa: SLF001
            controller._bookmarks_dialog.close()  # noqa: SLF001
    except Exception:
        pass
    controller._bookmarks_dialog = BookmarksDialog(
        parent=controller.window, actions=actions
    )  # noqa: SLF001
    controller._bookmarks_dialog.open()  # noqa: SLF001
