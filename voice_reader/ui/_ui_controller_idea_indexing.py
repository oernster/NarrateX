from __future__ import annotations

import threading
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.ideas_staging import stage_normalized_text
from voice_reader.shared.config import Config


def start_ideas_indexing(controller, *, book_id: str) -> None:
    """Start background indexing and begin polling for progress.

    Hard requirement: must not block the Qt/UI thread.
    """

    mgr = getattr(controller, "idea_indexing_manager", None)
    if mgr is None:
        return

    # Avoid re-entry while orchestration is in flight.
    if getattr(controller, "_ideas_launch_inflight", False):  # noqa: SLF001
        return
    controller._ideas_launch_inflight = True  # noqa: SLF001

    # Cancel any previous orchestration thread.
    try:
        if controller._ideas_launch_cancel is not None:  # noqa: SLF001
            controller._ideas_launch_cancel.set()  # noqa: SLF001
    except Exception:
        pass
    controller._ideas_launch_cancel = threading.Event()  # noqa: SLF001

    # Lightweight UI feedback only (do not touch multiprocessing here).
    # Do NOT write into lbl_status: narration overwrites it frequently.
    try:
        tip = "Mapping ideas… 0%"
        if hasattr(controller.window, "btn_ideas"):
            controller.window.btn_ideas.setToolTip(tip)
        if hasattr(controller.window, "ideas_progress"):
            controller.window.ideas_progress.setToolTip(tip)
    except Exception:
        pass

    # Show the dedicated Ideas progress bar (kept separate from narration progress).
    try:
        if hasattr(controller.window, "ideas_progress"):
            controller.window.ideas_progress.setVisible(True)
            controller.window.ideas_progress.setValue(0)
    except Exception:
        pass

    def _post_to_ui(fn) -> None:
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

    def _launcher() -> None:
        cancel_ev = controller._ideas_launch_cancel  # noqa: SLF001
        try:
            # Snapshot book metadata on the launcher thread (may still be large,
            # but avoids blocking the Qt loop).
            book_title = None
            normalized_text = ""
            try:
                book = getattr(
                    controller.narration_service, "_book", None
                )  # noqa: SLF001
                book_title = getattr(book, "title", None)
                normalized_text = str(getattr(book, "normalized_text", ""))
            except Exception:
                pass

            if cancel_ev is not None and cancel_ev.is_set():
                raise RuntimeError("Ideas launch cancelled")

            # Stage normalized text to an app-managed work dir.
            # app.py ensures directories; tests may not. Ensure directory exists.
            try:
                work_dir = Config.from_project_root(Path.cwd()).paths.ideas_work_dir
            except Exception:
                # Fallback for older/partial config stubs.
                work_dir = Path.cwd() / "cache" / "ideas_work"

            text_path = stage_normalized_text(
                work_dir=Path(work_dir),
                book_id=str(book_id),
                normalized_text=normalized_text,
            )

            if cancel_ev is not None and cancel_ev.is_set():
                # Avoid spawning if user switched books/app exited.
                from voice_reader.application.services.ideas_staging import safe_unlink

                safe_unlink(text_path)
                raise RuntimeError("Ideas launch cancelled")

            # Spawn process (can be expensive on Windows); keep off UI thread.
            mgr.start_indexing(
                book_id=book_id,
                book_title=str(book_title) if book_title is not None else None,
                text_path=str(text_path),
            )

            def _on_launched() -> None:
                controller._ideas_launch_inflight = False  # noqa: SLF001
                controller._ideas_index_job_book_id = book_id  # noqa: SLF001
                try:
                    from PySide6.QtCore import QTimer

                    if controller._ideas_index_timer is None:  # noqa: SLF001
                        controller._ideas_index_timer = QTimer(
                            controller.window
                        )  # noqa: SLF001
                        controller._ideas_index_timer.setInterval(50)  # noqa: SLF001
                        controller._ideas_index_timer.timeout.connect(
                            controller._poll_ideas_indexing
                        )
                    if controller._ideas_index_timer is not None:  # noqa: SLF001
                        controller._ideas_index_timer.start()  # noqa: SLF001
                    try:
                        controller._log.debug(  # noqa: SLF001
                            "Ideas: polling timer started book_id=%s interval_ms=%s",
                            str(book_id),
                            50,
                        )
                    except Exception:
                        pass
                except Exception:
                    controller._ideas_index_timer = None  # noqa: SLF001
                controller._poll_ideas_indexing()

            _post_to_ui(_on_launched)
        except Exception:

            def _on_failed() -> None:
                controller._ideas_launch_inflight = False  # noqa: SLF001
                # Do not leave polling stuck.
                try:
                    if controller._ideas_index_timer is not None:  # noqa: SLF001
                        controller._ideas_index_timer.stop()  # noqa: SLF001
                except Exception:
                    pass
                controller._ideas_index_job_book_id = None  # noqa: SLF001
                try:
                    controller.window.lbl_status.setText("Ideas mapping failed")
                except Exception:
                    pass

            _post_to_ui(_on_failed)

    t = threading.Thread(target=_launcher, name="IdeasLaunch", daemon=True)
    controller._ideas_launch_thread = t  # noqa: SLF001
    t.start()


def poll_ideas_indexing(controller) -> None:
    book_id = getattr(controller, "_ideas_index_job_book_id", None)  # noqa: SLF001
    if not book_id:
        return

    mgr = getattr(controller, "idea_indexing_manager", None)
    if mgr is None:
        return

    events = mgr.poll(book_id=book_id)

    # Optional deep debug: surface worker debug events into app logs.
    try:
        import os

        ideas_debug = os.getenv("NARRATEX_IDEAS_DEBUG", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
    except Exception:
        ideas_debug = False

    # Update UI (best-effort; do not break playback if anything fails).
    # Always drive the dedicated Ideas progress bar, regardless of playback state,
    # because it is separate from narration progress.
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "debug" and ideas_debug:
            try:
                controller._log.debug(
                    "Ideas worker: %s", str(ev.get("message") or "")
                )  # noqa: SLF001
            except Exception:
                pass
            continue
        if ev.get("type") == "progress":
            try:
                p = int(ev.get("progress") or 0)
            except Exception:
                p = 0
            try:
                msg = str(ev.get("message") or "Mapping ideas…")
            except Exception:
                msg = "Mapping ideas…"
            tip = f"{msg} {max(0, min(100, p))}%"
            try:
                if hasattr(controller.window, "btn_ideas"):
                    controller.window.btn_ideas.setToolTip(tip)
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setToolTip(tip)
            except Exception:
                pass
            try:
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setVisible(True)
                    controller.window.ideas_progress.setValue(max(0, min(100, p)))
            except Exception:
                pass
        elif ev.get("type") == "result":
            try:
                if hasattr(controller.window, "btn_ideas"):
                    controller.window.btn_ideas.setToolTip("Idea map ready")
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setToolTip("Idea map ready")
            except Exception:
                pass
            try:
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setValue(100)
                    controller.window.ideas_progress.setVisible(False)
            except Exception:
                pass
        elif ev.get("type") == "error":
            try:
                msg = str(ev.get("message") or "Ideas mapping failed")
            except Exception:
                msg = "Ideas mapping failed"
            try:
                if hasattr(controller.window, "btn_ideas"):
                    controller.window.btn_ideas.setToolTip(msg)
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setToolTip(msg)
            except Exception:
                pass
            try:
                if hasattr(controller.window, "ideas_progress"):
                    controller.window.ideas_progress.setValue(0)
                    controller.window.ideas_progress.setVisible(False)
            except Exception:
                pass

    # If we reached a terminal event, stop polling and re-evaluate search enabled state.
    if any(
        isinstance(ev, dict) and ev.get("type") in {"result", "error"} for ev in events
    ):
        try:
            if controller._ideas_index_timer is not None:  # noqa: SLF001
                controller._ideas_index_timer.stop()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass
        controller._ideas_index_job_book_id = None  # noqa: SLF001
        # Ensure the Ideas progress bar is hidden/reset.
        try:
            if hasattr(controller.window, "ideas_progress"):
                controller.window.ideas_progress.setValue(0)
                controller.window.ideas_progress.setVisible(False)
        except Exception:
            pass
        try:
            controller._apply_search_enabled_state()
        except Exception:  # pragma: no cover
            pass


def can_show_idea_progress(controller) -> bool:
    """Avoid overriding narration progress while playback is active."""

    try:
        st = getattr(controller.narration_service, "state", None)
        status = getattr(st, "status", None)
        return status in {
            NarrationStatus.IDLE,
            NarrationStatus.PAUSED,
            NarrationStatus.STOPPED,
            NarrationStatus.ERROR,
        }
    except Exception:  # pragma: no cover
        return True
