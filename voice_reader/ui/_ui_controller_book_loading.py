from __future__ import annotations

from pathlib import Path
import threading

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus

from voice_reader.ui._book_load_compute import LoadedBook, compute_loaded_book
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

    # Cancel any in-flight pre-synthesis from the previous book.
    try:
        cancel = getattr(controller, "_presynth_cancel", None)
        if cancel is not None:
            cancel.set()
    except Exception:
        pass


def _post_to_ui(controller, fn) -> None:
    # IMPORTANT:
    # Do not use QTimer.singleShot from a background thread. In PySide/Qt,
    # the timer is owned by the thread that creates it; a non-Qt thread
    # typically has no event loop, and the callback may never run.
    try:
        controller.ui_call_requested.emit(fn)
        return
    except Exception:
        pass

    # Best-effort fallback.
    try:
        fn()
    except Exception:
        return


def _start_presynthesis(controller) -> None:
    # Pre-synthesise the first chunks to cache so pressing Play is near-instant.
    try:
        presynth_fn = getattr(controller.narration_service, "presynthesize_start", None)
        voice = controller._selected_voice()  # noqa: SLF001
        if callable(presynth_fn) and voice is not None:
            cancel = threading.Event()
            controller._presynth_cancel = cancel  # noqa: SLF001
            threading.Thread(
                target=presynth_fn,
                args=(voice,),
                kwargs={"cancel_event": cancel},
                daemon=True,
                name="tts-presynth",
            ).start()
    except Exception:
        pass


def _apply_loaded_book(controller, *, loaded: LoadedBook) -> None:
    """Widget updates for a finished load. Runs on the Qt thread only."""

    book = loaded.book
    if loaded.plan is not None:
        try:
            controller.window.set_reader_document(loaded.plan)
        except Exception:
            controller._log.exception("Reader rendering failed")  # noqa: SLF001
            controller.window.set_reader_text(book.normalized_text)
    else:
        controller.window.set_reader_text(book.normalized_text)

    controller._chapters = list(loaded.chapters)  # noqa: SLF001
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
    apply_chapter_controls(controller, current_char_offset=int(loaded.start_char))

    try:
        controller.window.set_cover_image(loaded.cover)
    except Exception:
        controller._log.exception("Failed to set cover image")  # noqa: SLF001

    # Search enablement depends on idea indexing availability for this book.
    try:
        controller._apply_search_enabled_state()  # noqa: SLF001
    except Exception:
        pass

    _start_presynthesis(controller)


def _apply_load_failure(controller, *, path: Path, exc: Exception) -> None:
    """Surface a clear state in the UI instead of silently staying blank."""

    try:
        controller._log.exception("Book load failed: %s", path)  # noqa: SLF001
    except Exception:
        pass
    try:
        controller._chapters = []  # noqa: SLF001
    except Exception:
        pass
    try:
        if hasattr(controller.window, "chapter_spine"):
            controller.window.chapter_spine.set_chapters([])
            controller.window.chapter_spine.set_current_chapter(None)
            controller.window.chapter_spine.set_playhead_char_offset(None)
    except Exception:
        pass
    try:
        controller.window.set_cover_image(None)
    except Exception:
        pass
    try:
        controller.window.set_reader_text("")
    except Exception:
        pass

    try:
        controller.narration_service._set_state(  # noqa: SLF001
            NarrationState(
                status=NarrationStatus.ERROR,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Failed loading {path.name}: {exc}",
            )
        )
    except Exception:
        pass


def _set_loading_indicator(controller, *, active: bool, path: Path | None) -> None:
    """Visible feedback while a load runs: status text, animated bar, locks.

    The progress bar goes indeterminate (Qt's sliding fill) so the user sees
    motion for the whole load, and the controls that would race the load
    (selecting another book, starting playback of the outgoing book) are
    disabled, which the app styles as the red inert ring.
    """

    try:
        if active and path is not None:
            controller.window.lbl_status.setText(f"Loading {path.name}...")
    except Exception:
        pass
    try:
        if active:
            controller.window.progress.setRange(0, 0)
        else:
            controller.window.progress.setRange(0, 100)
            controller.window.progress.setValue(0)
    except Exception:
        pass
    # Disabling the focused control makes Qt hop focus to its neighbour
    # (the voice picker), which then paints its focus ring mid-load. Clear
    # focus first so the load runs with a neutral focus state.
    if active:
        try:
            from PySide6.QtWidgets import QApplication

            focused = QApplication.focusWidget()
            if focused is not None:
                focused.clearFocus()
        except Exception:
            pass
    for name in ("btn_select_book", "btn_play_pause", "btn_stop"):
        try:
            widget = getattr(controller.window, name, None)
            if widget is not None:
                widget.setEnabled(not active)
        except Exception:
            pass


def _loader_kwargs(controller, *, path: Path) -> dict:
    """The subprocess loader's inputs, read from the live app's own wiring.

    The chunker bounds and the converter's temp dir come from the running
    services rather than fresh literals, so the child process can never
    drift from what narration itself would build.
    """

    chunker = controller.narration_service.chunking_service
    temp_books_dir = controller.narration_service.book_repo.converter.temp_books_dir
    return {
        "path": path,
        "temp_books_dir": temp_books_dir,
        "chunk_min_chars": int(chunker.min_chars),
        "chunk_max_chars": int(chunker.max_chars),
    }


def _load_via_subprocess(controller, *, loader, path: Path) -> LoadedBook:
    """Run the parse in the child process, then adopt the book here.

    Adoption is the fast half of `load_book`: it swaps the service's book
    and emits the usual LOADING then IDLE states, so the state-driven UI
    (status label, button locks) behaves exactly as it always has.
    """

    result = loader(**_loader_kwargs(controller, path=path))
    if not isinstance(result, dict) or result.get("type") != "result":
        message = "book load failed"
        if isinstance(result, dict):
            message = str(result.get("message") or message)
        raise RuntimeError(message)

    book = result["book"]
    controller.narration_service.adopt_book(book, path)
    return LoadedBook(
        book=book,
        plan=result.get("plan"),
        chapters=tuple(result.get("chapters") or ()),
        start_char=int(result.get("start_char") or 0),
        cover=result.get("cover"),
    )


def load_selected_book(controller, *, path: Path) -> None:
    """Load a selected book without blocking the Qt/UI thread.

    A thread alone is not enough: the parse is CPU-bound pure Python, so a
    worker thread holds the GIL and starves the event loop regardless. The
    heavy pipeline therefore runs in a separate process (the same isolation
    Ideas indexing uses) and this thread only waits on the result queue,
    which releases the GIL. Widget updates come back through
    `ui_call_requested`. Without an injected loader (tests, or a platform
    where spawn fails) the compute falls back to running on this thread.
    """

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

    # One load at a time. The LOADING status lands asynchronously once the
    # load reaches the service, so this flag covers the gap in between.
    if getattr(controller, "_book_load_inflight", False):  # noqa: SLF001
        return

    prepare_for_book_switch(controller)
    controller._book_load_inflight = True  # noqa: SLF001
    _set_loading_indicator(controller, active=True, path=path)

    def _worker() -> None:
        loader = getattr(controller, "_book_loader", None)  # noqa: SLF001
        try:
            if loader is not None:
                loaded = _load_via_subprocess(controller, loader=loader, path=path)
            else:
                loaded = compute_loaded_book(controller, path=path)
        except Exception as exc:

            def _on_failed(exc: Exception = exc) -> None:
                controller._book_load_inflight = False  # noqa: SLF001
                _set_loading_indicator(controller, active=False, path=None)
                _apply_load_failure(controller, path=path, exc=exc)

            _post_to_ui(controller, _on_failed)
            return

        def _on_loaded() -> None:
            controller._book_load_inflight = False  # noqa: SLF001
            _set_loading_indicator(controller, active=False, path=None)
            _apply_loaded_book(controller, loaded=loaded)

        _post_to_ui(controller, _on_loaded)

    t = threading.Thread(target=_worker, name="book-load", daemon=True)
    controller._book_load_thread = t  # noqa: SLF001
    t.start()
