"""UI controller bridging PySide UI and application services.

This module is intentionally small; implementation details live in helper
modules under `voice_reader.ui._ui_controller_*`.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.chapter_index_service import ChapterIndexService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.idea_indexing_manager import IdeaIndexingManager
from voice_reader.application.services.structural_bookmark_service import (
    StructuralBookmarkService,
)
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.chapter import Chapter
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.infrastructure.books.cover_extractor import CoverExtractor
from voice_reader.ui._ui_controller_bookmarks import open_bookmarks_dialog
from voice_reader.ui._ui_controller_ideas import open_ideas_dialog
from voice_reader.ui._ui_controller_sections import open_structural_bookmarks_dialog
from voice_reader.ui._ui_controller_chapters import (
    apply_chapter_controls,
    next_chapter,
    previous_chapter,
)
from voice_reader.ui._ui_controller_playback import (
    pause,
    play,
    set_speed,
    set_volume,
    stop,
)
from voice_reader.ui._ui_controller_state import apply_state, on_state
from voice_reader.ui.main_window import MainWindow

from voice_reader.application.services.ideas_staging import stage_normalized_text
from voice_reader.shared.config import Config


class UiController(QObject):
    """Testable controller."""

    state_received = Signal(object)
    ui_call_requested = Signal(object)

    def __init__(
        self,
        *,
        window: MainWindow,
        narration_service: NarrationService,
        bookmark_service: BookmarkService,
        idea_map_service: IdeaMapService | None = None,
        idea_indexing_manager: IdeaIndexingManager | None = None,
        structural_bookmark_service: StructuralBookmarkService | None = None,
        voice_service: VoiceProfileService,
        device: str,
        engine_name: str,
    ) -> None:
        super().__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self.window = window
        self.narration_service = narration_service
        self.bookmark_service = bookmark_service
        self.idea_map_service = idea_map_service
        self.idea_indexing_manager = idea_indexing_manager
        self.structural_bookmark_service = (
            structural_bookmark_service or StructuralBookmarkService()
        )
        self.voice_service = voice_service
        self.device = device
        self.engine_name = engine_name

        self._voices: Sequence[VoiceProfile] = []
        self._last_prepared_voice_id: str | None = None
        self._cover_extractor = CoverExtractor()
        self._bookmarks_dialog = None
        self._ideas_dialog = None
        self._sections_dialog = None
        self._ideas_index_job_book_id: str | None = None
        self._ideas_index_timer = None
        self._ideas_launch_inflight: bool = False
        self._ideas_launch_cancel: threading.Event | None = None
        self._ideas_launch_thread: threading.Thread | None = None

        self._chapter_index_service = ChapterIndexService()
        self._chapters: list[Chapter] = []
        self._current_chapter: Chapter | None = None

        # Optional dependency for chapter indexing on load.
        try:
            detector = self.narration_service.reading_start_detector
        except Exception:
            detector = ReadingStartService()
        try:
            chunker = self.narration_service.chunking_service
        except Exception:
            chunker = None

        if chunker is None:
            self._navigation_chunk_service = None
        else:
            self._navigation_chunk_service = NavigationChunkService(
                reading_start_detector=detector,
                chunking_service=chunker,
            )

        try:
            self.window.set_chapter_controls_enabled(previous=False, next_=False)
        except Exception:
            pass

        try:
            self.window.lbl_device.setText(f"Device: {self.device}")
            self.window.lbl_engine.setText(f"Engine: {self.engine_name}")
        except Exception:
            pass

        self._connect_signals()

        # v1: search remains disabled until indexing exists. This is only a hook.
        try:
            self._apply_search_enabled_state()
        except Exception:
            pass

        # Keep the legacy method names for UI tests/backwards-compat.
        self.state_received.connect(self._apply_state)
        # Thread-safe UI posting: background threads may request a UI callback.
        # Qt will queue-deliver to the UI thread because this QObject lives there.
        self.ui_call_requested.connect(self._run_ui_callable)
        self.narration_service.add_listener(self.on_state)

        self.refresh_voices()

        # Initialize playback controls (session-only).
        try:
            self.set_speed("1.00x")
        except Exception:
            pass
        # Respect persisted/default volume by pulling from the service when possible.
        try:
            raw = getattr(self.narration_service, "playback_volume")()
            v = int(round(float(getattr(raw, "multiplier", 1.0)) * 100.0))
            self.set_volume(v)
        except Exception:
            try:
                self.set_volume(100)
            except Exception:
                pass

    @Slot(object)
    def _run_ui_callable(self, fn: object) -> None:
        """Execute a callable on the Qt UI thread (best-effort)."""

        try:
            if callable(fn):
                fn()
        except Exception:
            return

    def on_app_exit(self) -> None:
        """Best-effort cleanup for background tasks.

        NarrationService owns resume persistence; this only handles Ideas indexing
        so we don't leave a worker process running when the app exits.
        """

        # Sections feature owns no background work; only close the dialog.
        try:
            dlg = getattr(self, "_sections_dialog", None)  # noqa: SLF001
            if dlg is not None:
                dlg.close()
        except Exception:
            pass

        # Cancel any in-flight launcher orchestration.
        try:
            if self._ideas_launch_cancel is not None:
                self._ideas_launch_cancel.set()
        except Exception:  # pragma: no cover
            pass

        book_id = getattr(self, "_ideas_index_job_book_id", None)
        if not book_id:
            return
        mgr = getattr(self, "idea_indexing_manager", None)
        if mgr is not None:
            try:
                mgr.cancel(book_id=str(book_id))
            except Exception:  # pragma: no cover
                pass
        self._ideas_index_job_book_id = None
        try:
            if self._ideas_index_timer is not None:
                self._ideas_index_timer.stop()
        except Exception:  # pragma: no cover
            pass

    def on_state(self, state: NarrationState) -> None:
        """Receive narration state updates (may be called from a background thread)."""

        return on_state(self, state)

    def _apply_state(self, state: object) -> None:
        """Apply a narration state to the UI (runs on the Qt UI thread)."""

        return apply_state(self, state)

    def _connect_signals(self) -> None:
        self.window.select_book_clicked.connect(self.select_book)
        self.window.play_clicked.connect(self.play)
        self.window.pause_clicked.connect(self.pause)
        self.window.stop_clicked.connect(self.stop)

        if hasattr(self.window, "previous_chapter_clicked"):
            try:
                self.window.previous_chapter_clicked.connect(self.previous_chapter)
            except Exception:
                pass
        if hasattr(self.window, "next_chapter_clicked"):
            try:
                self.window.next_chapter_clicked.connect(self.next_chapter)
            except Exception:
                pass
        if hasattr(self.window, "bookmarks_clicked"):
            try:
                self.window.bookmarks_clicked.connect(self.open_bookmarks_dialog)
            except Exception:
                pass
        if hasattr(self.window, "ideas_clicked"):
            try:
                self.window.ideas_clicked.connect(self.open_sections_dialog)
            except Exception:
                pass
        if hasattr(self.window, "speed_changed"):
            try:
                self.window.speed_changed.connect(self.set_speed)
            except Exception:
                pass
        if hasattr(self.window, "volume_changed"):
            try:
                self.window.volume_changed.connect(self.set_volume)
            except Exception:
                pass

    def set_speed(self, text: str) -> None:
        return set_speed(self, text)

    def set_volume(self, value: int) -> None:
        return set_volume(self, value)

    def play(self) -> None:
        return play(self)

    def pause(self) -> None:
        return pause(self)

    def stop(self) -> None:
        return stop(self)

    def open_bookmarks_dialog(self) -> None:
        return open_bookmarks_dialog(self)

    def open_ideas_dialog(self) -> None:
        return open_ideas_dialog(self)

    def open_sections_dialog(self) -> None:
        return open_structural_bookmarks_dialog(self)

    def _start_ideas_indexing(self, *, book_id: str) -> None:
        """Start background indexing and begin polling for progress.

        Hard requirement: must not block the Qt/UI thread.
        """

        mgr = getattr(self, "idea_indexing_manager", None)
        if mgr is None:
            return

        # Avoid re-entry while orchestration is in flight.
        if getattr(self, "_ideas_launch_inflight", False):
            return
        self._ideas_launch_inflight = True

        # Cancel any previous orchestration thread.
        try:
            if self._ideas_launch_cancel is not None:
                self._ideas_launch_cancel.set()
        except Exception:
            pass
        self._ideas_launch_cancel = threading.Event()

        # Lightweight UI feedback only (do not touch multiprocessing here).
        # Do NOT write into lbl_status: narration overwrites it frequently.
        try:
            tip = "Mapping ideas… 0%"
            if hasattr(self.window, "btn_ideas"):
                self.window.btn_ideas.setToolTip(tip)
            if hasattr(self.window, "ideas_progress"):
                self.window.ideas_progress.setToolTip(tip)
        except Exception:
            pass

        # Show the dedicated Ideas progress bar (kept separate from narration progress).
        try:
            if hasattr(self.window, "ideas_progress"):
                self.window.ideas_progress.setVisible(True)
                self.window.ideas_progress.setValue(0)
        except Exception:
            pass

        def _post_to_ui(fn) -> None:
            # IMPORTANT:
            # Do not use QTimer.singleShot from a background thread. In PySide/Qt,
            # the timer is owned by the thread that creates it; a non-Qt thread
            # typically has no event loop, and the callback may never run.
            try:
                self.ui_call_requested.emit(fn)
                return
            except Exception:
                pass

            # Best-effort fallback.
            try:
                fn()
            except Exception:
                return

        def _launcher() -> None:
            cancel_ev = self._ideas_launch_cancel
            try:
                # Snapshot book metadata on the launcher thread (may still be large,
                # but avoids blocking the Qt loop).
                book_title = None
                normalized_text = ""
                try:
                    book = getattr(self.narration_service, "_book", None)  # noqa: SLF001
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
                    self._ideas_launch_inflight = False
                    self._ideas_index_job_book_id = book_id
                    try:
                        from PySide6.QtCore import QTimer

                        if self._ideas_index_timer is None:
                            self._ideas_index_timer = QTimer(self.window)
                            self._ideas_index_timer.setInterval(50)
                            self._ideas_index_timer.timeout.connect(
                                self._poll_ideas_indexing
                            )
                        if self._ideas_index_timer is not None:
                            self._ideas_index_timer.start()
                        try:
                            self._log.debug(
                                "Ideas: polling timer started book_id=%s interval_ms=%s",
                                str(book_id),
                                50,
                            )
                        except Exception:
                            pass
                    except Exception:
                        self._ideas_index_timer = None
                    self._poll_ideas_indexing()

                _post_to_ui(_on_launched)
            except Exception:
                def _on_failed() -> None:
                    self._ideas_launch_inflight = False
                    # Do not leave polling stuck.
                    try:
                        if self._ideas_index_timer is not None:
                            self._ideas_index_timer.stop()
                    except Exception:
                        pass
                    self._ideas_index_job_book_id = None
                    try:
                        self.window.lbl_status.setText("Ideas mapping failed")
                    except Exception:
                        pass

                _post_to_ui(_on_failed)

        t = threading.Thread(target=_launcher, name="IdeasLaunch", daemon=True)
        self._ideas_launch_thread = t
        t.start()

    def _can_show_idea_progress(self) -> bool:
        """Avoid overriding narration progress while playback is active."""

        try:
            st = getattr(self.narration_service, "state", None)
            status = getattr(st, "status", None)
            from voice_reader.application.dto.narration_state import NarrationStatus

            return status in {
                NarrationStatus.IDLE,
                NarrationStatus.PAUSED,
                NarrationStatus.STOPPED,
                NarrationStatus.ERROR,
            }
        except Exception:  # pragma: no cover
            return True

    def _poll_ideas_indexing(self) -> None:
        book_id = getattr(self, "_ideas_index_job_book_id", None)
        if not book_id:
            return

        mgr = getattr(self, "idea_indexing_manager", None)
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
                    self._log.debug("Ideas worker: %s", str(ev.get("message") or ""))
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
                    if hasattr(self.window, "btn_ideas"):
                        self.window.btn_ideas.setToolTip(tip)
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setToolTip(tip)
                except Exception:
                    pass
                try:
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setVisible(True)
                        self.window.ideas_progress.setValue(max(0, min(100, p)))
                except Exception:
                    pass
            elif ev.get("type") == "result":
                try:
                    if hasattr(self.window, "btn_ideas"):
                        self.window.btn_ideas.setToolTip("Idea map ready")
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setToolTip("Idea map ready")
                except Exception:
                    pass
                try:
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setValue(100)
                        self.window.ideas_progress.setVisible(False)
                except Exception:
                    pass
            elif ev.get("type") == "error":
                try:
                    msg = str(ev.get("message") or "Ideas mapping failed")
                except Exception:
                    msg = "Ideas mapping failed"
                try:
                    if hasattr(self.window, "btn_ideas"):
                        self.window.btn_ideas.setToolTip(msg)
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setToolTip(msg)
                except Exception:
                    pass
                try:
                    if hasattr(self.window, "ideas_progress"):
                        self.window.ideas_progress.setValue(0)
                        self.window.ideas_progress.setVisible(False)
                except Exception:
                    pass

        # If we reached a terminal event, stop polling and re-evaluate search enabled state.
        if any(
            isinstance(ev, dict) and ev.get("type") in {"result", "error"}
            for ev in events
        ):
            try:
                if self._ideas_index_timer is not None:
                    self._ideas_index_timer.stop()
            except Exception:  # pragma: no cover
                pass
            self._ideas_index_job_book_id = None
            # Ensure the Ideas progress bar is hidden/reset.
            try:
                if hasattr(self.window, "ideas_progress"):
                    self.window.ideas_progress.setValue(0)
                    self.window.ideas_progress.setVisible(False)
            except Exception:
                pass
            try:
                self._apply_search_enabled_state()
            except Exception:  # pragma: no cover
                pass


    def _apply_search_enabled_state(self) -> None:
        """Enable 🔎 only when a completed idea index exists for the loaded book."""

        # Search removed from UI.
        return

    def previous_chapter(self) -> None:
        return previous_chapter(self)

    def next_chapter(self) -> None:
        return next_chapter(self)

    def refresh_voices(self) -> None:
        voices = [v for v in self.voice_service.list_profiles() if v.name != "system"]
        voices.sort(key=lambda v: self._voice_label(v).casefold())
        self._voices = voices

        self.window.voice_combo.clear()
        for v in self._voices:
            self.window.voice_combo.addItem(self._voice_label(v), v.name)
        if not self._voices:
            self.window.voice_combo.addItem("(no voices found)")

    def select_book(self) -> None:
        # Prevent book switching during playback/preparation. The UI should already
        # disable the button, but keep this as a safety net (signals/tests can call
        # the handler directly).
        try:
            st = getattr(self.narration_service, "state", None)
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

        # Resilience: if an Ideas indexing job is running for a previous book,
        # cancel it before switching books. Indexing can always be restarted.
        try:
            old_id = self.narration_service.loaded_book_id()
        except Exception:
            old_id = None
        if old_id and getattr(self, "_ideas_index_job_book_id", None) == old_id:
            mgr = getattr(self, "idea_indexing_manager", None)
            if mgr is not None:
                try:
                    mgr.cancel(book_id=old_id)
                except Exception:  # pragma: no cover
                    pass
            self._ideas_index_job_book_id = None
            try:
                if self._ideas_index_timer is not None:
                    self._ideas_index_timer.stop()
            except Exception:  # pragma: no cover
                pass

        # Also cancel any in-flight launch orchestration.
        try:
            if self._ideas_launch_cancel is not None:
                self._ideas_launch_cancel.set()
        except Exception:  # pragma: no cover
            pass
        self._ideas_launch_inflight = False

        path_str, _ = QFileDialog.getOpenFileName(
            self.window,
            "Select Book",
            str(Path.cwd()),
            "Books (*.epub *.pdf *.txt *.mobi *.azw *.azw3 *.prc *.kfx);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        book = self.narration_service.load_book(path)
        self.window.set_reader_text(book.normalized_text)

        start_char_for_ui = 0
        try:
            if self._navigation_chunk_service is not None:
                chunks, start = self._navigation_chunk_service.build_chunks(
                    book_text=book.normalized_text
                )
                start_char_for_ui = int(start.start_char)
                self._chapters = self._chapter_index_service.build_index(
                    book.normalized_text,
                    chunks=chunks,
                    min_char_offset=int(start.start_char),
                )
            else:
                self._chapters = []
        except Exception:
            self._log.exception("Chapter index build failed")
            self._chapters = []

        try:
            if hasattr(self.window, "chapter_spine"):
                self.window.chapter_spine.set_chapters(self._chapters)
                self.window.chapter_spine.set_current_chapter(None)
        except Exception:
            pass
        apply_chapter_controls(self, current_char_offset=int(start_char_for_ui))

        try:
            cover = self._cover_extractor.extract_cover_bytes(path)
        except Exception:
            self._log.exception("Cover extraction failed")
            cover = None
        try:
            self.window.set_cover_image(cover)
        except Exception:
            self._log.exception("Failed to set cover image")

        # Search enablement depends on idea indexing availability for this book.
        try:
            self._apply_search_enabled_state()
        except Exception:
            pass

    def _selected_voice(self) -> VoiceProfile | None:
        if not self._voices:
            return None
        name = (
            self.window.voice_combo.currentData()
            or self.window.voice_combo.currentText()
        )
        for v in self._voices:
            if v.name == name:
                return v
        return self._voices[0]

    @staticmethod
    def _voice_label(voice: VoiceProfile) -> str:
        parts = voice.name.split("_", 1)
        if len(parts) == 2 and len(parts[0]) == 2:
            prefix, raw_name = parts
            region_label = {"b": "British", "a": "American"}.get(prefix[0])
            gender_label = {"f": "Female", "m": "Male"}.get(prefix[1])
            name_label = raw_name.replace("-", " ").replace("_", " ").title()
            if region_label and gender_label:
                return f"{name_label} ({region_label} {gender_label})"
        return voice.name.replace("_", " ").strip().title()
