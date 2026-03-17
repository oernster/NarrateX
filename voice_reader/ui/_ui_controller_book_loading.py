from __future__ import annotations

from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus

from voice_reader.ui._ui_controller_chapters import apply_chapter_controls


def prepare_for_book_switch(controller) -> None:
    """Cancel any per-book background work before switching books."""

    # Resilience: if an Ideas indexing job is running for a previous book,
    # cancel it before switching books. Indexing can always be restarted.
    try:
        old_id = controller.narration_service.loaded_book_id()
    except Exception:
        old_id = None
    if (
        old_id and getattr(controller, "_ideas_index_job_book_id", None) == old_id
    ):  # noqa: SLF001
        mgr = getattr(controller, "idea_indexing_manager", None)
        if mgr is not None:
            try:
                mgr.cancel(book_id=old_id)
            except Exception:  # pragma: no cover
                pass
        controller._ideas_index_job_book_id = None  # noqa: SLF001
        try:
            if controller._ideas_index_timer is not None:  # noqa: SLF001
                controller._ideas_index_timer.stop()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass

    # Also cancel any in-flight launch orchestration.
    try:
        if controller._ideas_launch_cancel is not None:  # noqa: SLF001
            controller._ideas_launch_cancel.set()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass
    controller._ideas_launch_inflight = False  # noqa: SLF001


def load_selected_book(controller, *, path: Path) -> None:
    """Load a selected book path and update UI state (best-effort)."""

    # Prevent book switching during playback/preparation. The UI should already
    # disable the button, but keep this as a safety net (signals/tests can call
    # the handler directly).
    try:
        st = getattr(controller.narration_service, "state", None)
        if isinstance(st, NarrationState) and st.status in {
            NarrationStatus.LOADING,
            NarrationStatus.CHUNKING,
            NarrationStatus.SYNTHESIZING,
            NarrationStatus.PLAYING,
        }:
            return
    except Exception:
        # Never block book selection due to an introspection error.
        pass

    prepare_for_book_switch(controller)

    book = controller.narration_service.load_book(path)
    controller.window.set_reader_text(book.normalized_text)

    start_char_for_ui = 0
    try:
        if controller._navigation_chunk_service is not None:  # noqa: SLF001
            chunks, start = controller._navigation_chunk_service.build_chunks(
                book_text=book.normalized_text
            )
            start_char_for_ui = int(start.start_char)
            controller._chapters = (
                controller._chapter_index_service.build_index(  # noqa: SLF001
                    book.normalized_text,
                    chunks=chunks,
                    min_char_offset=int(start.start_char),
                )
            )
        else:
            controller._chapters = []  # noqa: SLF001
    except Exception:
        controller._log.exception("Chapter index build failed")  # noqa: SLF001
        controller._chapters = []  # noqa: SLF001

    try:
        if hasattr(controller.window, "chapter_spine"):
            controller.window.chapter_spine.set_chapters(
                controller._chapters
            )  # noqa: SLF001
            controller.window.chapter_spine.set_current_chapter(None)
            # Avoid showing a stale playhead from the previously opened book.
            controller.window.chapter_spine.set_playhead_char_offset(None)
    except Exception:
        pass
    apply_chapter_controls(controller, current_char_offset=int(start_char_for_ui))

    try:
        cover = controller._cover_extractor.extract_cover_bytes(path)  # noqa: SLF001
    except Exception:
        controller._log.exception("Cover extraction failed")  # noqa: SLF001
        cover = None
    try:
        controller.window.set_cover_image(cover)
    except Exception:
        controller._log.exception("Failed to set cover image")  # noqa: SLF001

    # Search enablement depends on idea indexing availability for this book.
    try:
        controller._apply_search_enabled_state()  # noqa: SLF001
    except Exception:
        pass
