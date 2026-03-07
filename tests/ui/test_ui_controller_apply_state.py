from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


@dataclass
class FakeNarration:
    listeners: list

    def add_listener(self, listener):
        self.listeners.append(listener)


@dataclass(frozen=True, slots=True)
class FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="system", reference_audio_paths=[])]


def test_ui_controller_apply_state_updates_widgets(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(listeners=[])
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )
    state = NarrationState(
        status=NarrationStatus.PLAYING,
        current_chunk_id=0,
        total_chunks=10,
        progress=0.5,
        message="Playing",
        highlight_start=0,
        highlight_end=3,
    )
    c._apply_state(state)  # pylint: disable=protected-access
    assert "1/10" in w.lbl_progress.text()
