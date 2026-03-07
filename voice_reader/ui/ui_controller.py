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
        self._voices = list(self.voice_service.list_profiles())
        self.window.voice_combo.clear()
        for v in self._voices:
            self.window.voice_combo.addItem(v.name)
        if not self._voices:
            self.window.voice_combo.addItem("(no voices found)")
        self.window.append_log(f"Loaded {len(self._voices)} voice profiles")

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
        self.window.append_log(f"Selected book: {book.title}")

    def _selected_voice(self) -> VoiceProfile | None:
        if not self._voices:
            return None
        name = self.window.voice_combo.currentText()
        for v in self._voices:
            if v.name == name:
                return v
        return self._voices[0]

    def play(self) -> None:
        # Semantics:
        # - If paused: resume (replay current chunk from beginning)
        # - If stopped/idle: (re)prepare and start from beginning
        # - If already playing: no-op
        st = getattr(self.narration_service, "state", None)
        if isinstance(st, NarrationState):
            if st.status == NarrationStatus.PAUSED:
                self.narration_service.resume()
                return
            if st.status == NarrationStatus.PLAYING:
                return

        voice = self._selected_voice()
        if voice is None:
            self.window.append_log("No voice profiles available")
            return

        self.narration_service.prepare(voice=voice)
        self.narration_service.start()

    def pause(self) -> None:
        self.narration_service.pause()

    def stop(self) -> None:
        self.narration_service.stop()

    def on_state(self, state: NarrationState) -> None:
        # Called from background thread.
        self.state_received.emit(state)

    def _apply_state(self, state: object) -> None:
        if not isinstance(state, NarrationState):
            return
        self.window.append_log(f"{state.status.value}: {state.message}")
        if state.status.value == "chunking":
            # Surface why we are skipping/where we start.
            self._log.info("%s", state.message)
        if state.total_chunks:
            self.window.lbl_progress.setText(
                f"{(state.current_chunk_id or 0) + 1}/{state.total_chunks}"
            )
        self.window.progress.setValue(int(state.progress * 100))
        self.window.highlight_range(state.highlight_start, state.highlight_end)
