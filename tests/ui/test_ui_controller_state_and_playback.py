"""Applying narration state to the window, and the playback controls.

Separated from the book-selection tests: those cover what happens when a reader
opens something, these cover what happens while it plays.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui.ui_controller_fakes import (
    FakeBookmarks,
    FakeIdeasRepo,
    FakeNarration,
    FakeVoiceRepo,
)


def test_on_state_ignores_runtime_error_on_emit(monkeypatch, qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    # Patch the controller's SignalInstance to a stub that raises RuntimeError.
    # SignalInstance.emit is read-only, so replace the attribute entirely.
    monkeypatch.setattr(
        c,
        "state_received",
        SimpleNamespace(emit=lambda state: (_ for _ in ()).throw(RuntimeError("dead"))),
    )
    c.on_state(narration.state)


def test_apply_state_ignores_non_state(monkeypatch, qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )
    c._apply_state(object())  # pylint: disable=protected-access


def test_speed_changed_calls_service(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    # Drive controller logic directly (signal wiring covered by smoke tests).
    c.set_speed("1.25x")
    assert narration.last_rate == 1.25


def test_volume_changed_calls_service_and_maps_slider(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo(profiles=[]))
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo(doc=None)),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    c.set_volume(50)
    assert narration.last_volume == 0.5

    c.set_volume(0)
    assert narration.last_volume == 0.0

    c.set_volume(100)
    assert narration.last_volume == 1.0
