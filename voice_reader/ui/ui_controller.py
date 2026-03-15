"""UI controller bridging PySide UI and application services.

This module is intentionally small; implementation details live in helper
modules under `voice_reader.ui._ui_controller_*`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from voice_reader.application.dto.narration_state import NarrationState
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.chapter_index_service import ChapterIndexService
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


class UiController(QObject):
    """Testable controller."""

    state_received = Signal(object)

    def __init__(
        self,
        *,
        window: MainWindow,
        narration_service: NarrationService,
        bookmark_service: BookmarkService,
        voice_service: VoiceProfileService,
        device: str,
        engine_name: str,
    ) -> None:
        super().__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self.window = window
        self.narration_service = narration_service
        self.bookmark_service = bookmark_service
        self.voice_service = voice_service
        self.device = device
        self.engine_name = engine_name

        self._voices: Sequence[VoiceProfile] = []
        self._last_prepared_voice_id: str | None = None
        self._cover_extractor = CoverExtractor()
        self._bookmarks_dialog = None

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

        # Keep the legacy method names for UI tests/backwards-compat.
        self.state_received.connect(self._apply_state)
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
