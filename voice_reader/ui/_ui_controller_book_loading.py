from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.domain.document.reading_start import contents_end_offset
from voice_reader.domain.document.render_plan import build_render_plan

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


@dataclass(frozen=True, slots=True)
class _LoadedBook:
    """Everything a finished load hands back to the UI thread in one piece."""

    book: object
    plan: object | None
    chapters: tuple
    start_char: int
    cover: bytes | None


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


def _compute_render_plan(controller, *, book):
    """The book's render plan, or None when raw text should win.

    The fallback is not decoration. A book whose extraction was too poor to
    structure carries an unstructured document, and if rendering it would show
    the reader less than the raw text does, the raw text wins. Displaying
    something imperfect beats displaying almost nothing.
    """

    document = getattr(book, "document", None)
    if document is None:
        return None
    try:
        plan = build_render_plan(
            document,
            body_start=contents_end_offset(document),
        )
        if plan.text.strip():
            return plan
    except Exception:
        controller._log.exception("Reader rendering failed")  # noqa: SLF001
    return None


def _build_chapter_index(controller, *, book, chunks, min_char_offset: int):
    """Chapter anchors from the model where possible, else by detection.

    The model knows its own sections, so it needs no heading regex and finds
    prologues, named parts and subsections that the pattern cannot. Detection
    remains the fallback for a book with no usable structure.
    """

    service = controller._chapter_index_service  # noqa: SLF001
    document = getattr(book, "document", None)
    sections = getattr(document, "sections", ()) if document is not None else ()

    if sections:
        # Navigation is filtered by where the body begins, so the list
        # matches what the pane shows: every entry lands on visible text.
        chapters = service.build_index_from_sections(
            sections=sections,
            chunks=chunks,
            min_char_offset=contents_end_offset(document),
        )
        if chapters:
            return chapters

    return service.build_index(
        book.normalized_text,
        chunks=chunks,
        min_char_offset=min_char_offset,
    )


def _compute_loaded_book(controller, *, path: Path) -> _LoadedBook:
    """Everything expensive about opening a book, safe off the Qt thread.

    Parsing the file, building the render plan, the chapter index and the
    cover are pure service work: no widget is touched here, so a worker
    thread can run the whole thing while the UI stays live.
    """

    book = controller.narration_service.load_book(path)

    plan = _compute_render_plan(controller, book=book)

    start_char_for_ui = 0
    chapters: list = []
    try:
        if controller._navigation_chunk_service is not None:  # noqa: SLF001
            chunks, start = controller._navigation_chunk_service.build_chunks(
                book_text=book.normalized_text,
                document=book.document_model,
            )
            start_char_for_ui = int(start.start_char)
            chapters = _build_chapter_index(
                controller,
                book=book,
                chunks=chunks,
                min_char_offset=int(start.start_char),
            )
    except Exception:
        controller._log.exception("Chapter index build failed")  # noqa: SLF001
        chapters = []

    try:
        cover = controller._cover_extractor.extract_cover_bytes(path)  # noqa: SLF001
    except Exception:
        controller._log.exception("Cover extraction failed")  # noqa: SLF001
        cover = None

    return _LoadedBook(
        book=book,
        plan=plan,
        chapters=tuple(chapters),
        start_char=start_char_for_ui,
        cover=cover,
    )


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


def _apply_loaded_book(controller, *, loaded: _LoadedBook) -> None:
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


def load_selected_book(controller, *, path: Path) -> None:
    """Load a selected book on a worker thread, keeping the Qt loop live.

    Hard requirement: must not block the Qt/UI thread. Parsing a large book
    (the combined hardback in particular) takes long enough to freeze the
    window when run inline, so the heavy pipeline runs on a daemon thread
    and only the widget updates come back, posted through
    `ui_call_requested` exactly as the Ideas launcher does.
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
    # worker reaches the service, so this flag covers the gap in between.
    if getattr(controller, "_book_load_inflight", False):  # noqa: SLF001
        return

    prepare_for_book_switch(controller)
    controller._book_load_inflight = True  # noqa: SLF001

    # Immediate feedback while the worker spins up.
    try:
        controller.window.lbl_status.setText(f"Loading {path.name}...")
    except Exception:
        pass

    def _worker() -> None:
        try:
            loaded = _compute_loaded_book(controller, path=path)
        except Exception as exc:

            def _on_failed(exc: Exception = exc) -> None:
                controller._book_load_inflight = False  # noqa: SLF001
                _apply_load_failure(controller, path=path, exc=exc)

            _post_to_ui(controller, _on_failed)
            return

        def _on_loaded() -> None:
            controller._book_load_inflight = False  # noqa: SLF001
            _apply_loaded_book(controller, loaded=loaded)

        _post_to_ui(controller, _on_loaded)

    t = threading.Thread(target=_worker, name="book-load", daemon=True)
    controller._book_load_thread = t  # noqa: SLF001
    t.start()
