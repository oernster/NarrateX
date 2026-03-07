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
    state: NarrationState
    prepare_calls: int = 0
    start_calls: int = 0
    resume_calls: int = 0
    stop_calls: int = 0

    def add_listener(self, listener):
        self.listeners.append(listener)

    def prepare(self, *, voice, start_playback_index=None):
        del start_playback_index
        del voice
        self.prepare_calls += 1

    def start(self):
        self.start_calls += 1

    def resume(self):
        self.resume_calls += 1

    def pause(self):
        return

    def stop(self):
        self.stop_calls += 1
        return


@dataclass(frozen=True, slots=True)
class FakeVoiceRepo:
    def list_profiles(self):
        # Intentionally unsorted.
        return [
            VoiceProfile(name="bm_george", reference_audio_paths=[]),
            VoiceProfile(name="system", reference_audio_paths=[]),
            VoiceProfile(name="af_heart", reference_audio_paths=[]),
        ]


def test_play_when_paused_calls_resume(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=3,
            total_chunks=10,
            progress=0.3,
            message="Paused",
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    c.play()
    assert narration.resume_calls == 1
    assert narration.stop_calls == 0
    assert narration.prepare_calls == 0
    assert narration.start_calls == 0


def test_play_when_paused_and_voice_changed_restarts(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message="Idle",
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Start with default selection: system.
    c.play()
    assert narration.prepare_calls == 1
    assert narration.start_calls == 1

    # Now simulate paused playback.
    narration.state = NarrationState(
        status=NarrationStatus.PAUSED,
        current_chunk_id=3,
        total_chunks=10,
        progress=0.1,
        message="Paused",
    )

    # User selects a different voice while paused.
    # Find a non-system voice (sorted order should be deterministic).
    w.voice_combo.setCurrentIndex(1)
    c.play()
    assert narration.stop_calls == 1
    assert narration.resume_calls == 0
    # And it should start new narration.
    assert narration.prepare_calls == 2
    assert narration.start_calls == 2


def test_voice_dropdown_sorted_alphabetically_with_system_first(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message="Idle",
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    labels = [w.voice_combo.itemText(i) for i in range(w.voice_combo.count())]
    assert not any("system" in s.lower() for s in labels)
    assert labels == sorted(labels, key=lambda s: s.casefold())


def test_play_when_idle_prepares_and_starts(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message="Idle",
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    c.play()
    assert narration.prepare_calls == 1
    assert narration.start_calls == 1
    assert narration.resume_calls == 0
