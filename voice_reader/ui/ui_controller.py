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

from voice_reader.application.dto.narration_state import NarrationState
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
from voice_reader.application.interfaces.cover_extractor import CoverExtractor
from voice_reader.ui._ui_controller_bookmarks import open_bookmarks_dialog
from voice_reader.ui._ui_controller_ideas import open_ideas_dialog
from voice_reader.ui._ui_controller_sections import open_structural_bookmarks_dialog
from voice_reader.ui._ui_controller_chapters import next_chapter, previous_chapter
from voice_reader.ui._ui_controller_playback import (
    pause,
    play,
    set_speed,
    set_volume,
    stop,
    toggle_play_pause,
)
from voice_reader.ui._ui_controller_state import apply_state, on_state
from voice_reader.ui.main_window import MainWindow

from voice_reader.ui._ui_controller_book_loading import (
    load_selected_book,
    prepare_for_book_switch,
)
from voice_reader.ui._ui_controller_idea_indexing import (
    can_show_idea_progress,
    poll_ideas_indexing,
    start_ideas_indexing,
)


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
        cover_extractor: CoverExtractor | None = None,
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
        self._cover_extractor: CoverExtractor = cover_extractor or _NullCoverExtractor()
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
                # If the service volume isn't available, fall back to the
                # product default (25%).
                self.set_volume(25)
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

        # Playback transport:
        # - new UI uses a single play/pause toggle
        # - keep legacy separate play/pause signals for backwards compatibility
        if hasattr(self.window, "play_pause_clicked"):
            try:
                self.window.play_pause_clicked.connect(self.toggle_play_pause)
            except Exception:
                pass
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

    def toggle_play_pause(self) -> None:
        return toggle_play_pause(self)

    def open_bookmarks_dialog(self) -> None:
        return open_bookmarks_dialog(self)

    def open_ideas_dialog(self) -> None:
        return open_ideas_dialog(self)

    def open_sections_dialog(self) -> None:
        return open_structural_bookmarks_dialog(self)

    def _start_ideas_indexing(self, *, book_id: str) -> None:
        return start_ideas_indexing(self, book_id=book_id)

    def _can_show_idea_progress(self) -> bool:
        return can_show_idea_progress(self)

    def _poll_ideas_indexing(self) -> None:
        return poll_ideas_indexing(self)

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
        prepare_for_book_switch(self)

        path_str, _ = QFileDialog.getOpenFileName(
            self.window,
            "Select Book",
            str(Path.cwd()),
            "Books (*.epub *.pdf *.txt *.mobi *.azw *.azw3 *.prc *.kfx);;All Files (*)",
        )
        if not path_str:
            return

        load_selected_book(self, path=Path(path_str))

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


class _NullCoverExtractor:
    """UI-safe default when no cover extraction is wired.

    Real infrastructure wiring must happen in composition roots.
    """

    def extract_cover_bytes(self, source_path: Path) -> bytes | None:
        del source_path
        return None
