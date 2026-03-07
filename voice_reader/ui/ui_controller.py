"""UI controller bridging PySide UI and application services."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from voice_reader.application.dto.narration_state import NarrationState
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.infrastructure.books.cover_extractor import CoverExtractor
from voice_reader.ui.main_window import MainWindow


class UiController(QObject):
    """Testable controller.

    Receives narration state updates from a background thread and updates the UI
    via a Qt queued signal to stay thread-safe.
    """

    state_received = Signal(object)

    def __init__(
        self,
        *,
        window: MainWindow,
        narration_service: NarrationService,
        voice_service: VoiceProfileService,
        device: str,
        engine_name: str,
    ) -> None:
        super().__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self.window = window
        self.narration_service = narration_service
        self.voice_service = voice_service
        self.device = device
        self.engine_name = engine_name
        self._voices: Sequence[VoiceProfile] = []
        self._last_prepared_voice_id: str | None = None
        self._cover_extractor = CoverExtractor()

        self.window.lbl_device.setText(f"Device: {self.device}")
        self.window.lbl_engine.setText(f"Engine: {self.engine_name}")

        self.window.select_book_clicked.connect(self.select_book)
        self.window.play_clicked.connect(self.play)
        self.window.pause_clicked.connect(self.pause)
        self.window.stop_clicked.connect(self.stop)

        self.state_received.connect(self._apply_state)
        self.narration_service.add_listener(self.on_state)
        self.refresh_voices()

    def refresh_voices(self) -> None:
        voices = [v for v in self.voice_service.list_profiles() if v.name != "system"]
        # Sort alphabetically by the human-readable label.
        voices.sort(key=lambda v: self._voice_label(v).casefold())
        self._voices = voices
        self.window.voice_combo.clear()
        for v in self._voices:
            # Show a friendly name but keep the underlying voice ID recoverable.
            # We store the internal ID in the item's data so selection works even
            # when the display label is prettified.
            self.window.voice_combo.addItem(self._voice_label(v), v.name)
        if not self._voices:
            self.window.voice_combo.addItem("(no voices found)")
        self._log.debug("Loaded %s voice profiles", len(self._voices))

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

        # Best-effort cover extraction (EPUB/PDF). Non-blocking would be nicer,
        # but extraction is fast and failure is silent.
        try:
            cover = self._cover_extractor.extract_cover_bytes(path)
        except Exception:
            cover = None
        try:
            self.window.set_cover_image(cover)
        except Exception:
            # If the window implementation changes, don't fail book loading.
            pass
        self._log.info("Selected book: %s", book.title)

    def _selected_voice(self) -> VoiceProfile | None:
        if not self._voices:
            return None
        # Prefer resolving by stored internal ID (combo item data). Fallback to
        # currentText for older/placeholder items.
        name = self.window.voice_combo.currentData() or self.window.voice_combo.currentText()
        for v in self._voices:
            if v.name == name:
                return v
        return self._voices[0]

    @staticmethod
    def _voice_label(voice: VoiceProfile) -> str:
        """Convert internal voice IDs into human readable dropdown labels."""

        # Kokoro voice IDs: <region><gender>_<name>, e.g. bf_emma, am_michael.
        parts = voice.name.split("_", 1)
        if len(parts) == 2 and len(parts[0]) == 2:
            prefix, raw_name = parts
            region = prefix[0]
            gender = prefix[1]

            region_label = {"b": "British", "a": "American"}.get(region)
            gender_label = {"f": "Female", "m": "Male"}.get(gender)
            name_label = raw_name.replace("-", " ").replace("_", " ").title()

            if region_label and gender_label:
                return f"{name_label} ({region_label} {gender_label})"

        # Default: prettify snake-case while keeping user voice names readable.
        return voice.name.replace("_", " ").strip().title()

    def play(self) -> None:
        # Semantics:
        # - If paused: resume (replay current chunk from beginning)
        # - If stopped/idle: (re)prepare and start from beginning
        # - If already playing: no-op
        start_playback_index: int | None = None
        st = getattr(self.narration_service, "state", None)
        if isinstance(st, NarrationState):
            if st.status == NarrationStatus.PAUSED:
                # If user changed the voice while paused, apply it by restarting
                # narration with a new prepare()+start() rather than resuming.
                voice = self._selected_voice()
                if (
                    voice is not None
                    and self._last_prepared_voice_id is not None
                    and voice.name != self._last_prepared_voice_id
                ):
                    # Restart from the *current* chunk (chunk-level semantics).
                    # Capture before stop() resets state.
                    start_playback_index = int(st.current_chunk_id or 0)
                    self.narration_service.stop()
                else:
                    self.narration_service.resume()
                    return
            if st.status == NarrationStatus.PLAYING:
                return

        voice = self._selected_voice()
        if voice is None:
            self._log.warning("No voice profiles available")
            return

        self._last_prepared_voice_id = voice.name

        self._log.debug("Selected voice: %s (engine: %s)", voice.name, self.engine_name)

        self.narration_service.prepare(
            voice=voice,
            start_playback_index=start_playback_index,
        )
        self.narration_service.start()

    def pause(self) -> None:
        self.narration_service.pause()

    def stop(self) -> None:
        self.narration_service.stop()

    def on_state(self, state: NarrationState) -> None:
        # Called from background thread.
        try:
            self.state_received.emit(state)
        except RuntimeError:
            # QObject already destroyed; ignore late updates.
            return

    def _apply_state(self, state: object) -> None:
        if not isinstance(state, NarrationState):
            return
        # Keep UI log clean; use Python logging for verbose state transitions.
        self._log.debug("%s: %s", state.status.value, state.message)
        if state.status.value == "chunking":
            # Surface why we are skipping/where we start.
            self._log.info("%s", state.message)
        if state.total_chunks:
            self.window.lbl_progress.setText(
                f"{(state.current_chunk_id or 0) + 1}/{state.total_chunks}"
            )
        self.window.progress.setValue(int(state.progress * 100))
        self.window.highlight_range(state.highlight_start, state.highlight_end)
