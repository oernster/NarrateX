from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui._fakes_ideas_repo import FakeIdeasRepo


@dataclass
class FakeNarration:
    listeners: list
    state: NarrationState

    def add_listener(self, listener):
        self.listeners.append(listener)

    def prepare(
        self,
        *,
        voice,
        start_playback_index=None,
        start_char_offset=None,
        force_start_char=None,
        skip_essay_index=True,
        persist_resume=True,
    ):
        del (
            voice,
            start_playback_index,
            start_char_offset,
            force_start_char,
            skip_essay_index,
            persist_resume,
        )

    def start(self):
        return None

    def resume(self):
        return None

    def pause(self):
        return None

    def stop(self):
        return None

    def loaded_book_id(self):
        return "book-1"


@dataclass
class FakeBookmarks:
    resume_position: object | None = None

    def list_bookmarks(self, *, book_id: str):
        del book_id
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index
        return None

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        del book_id, bookmark_id

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return self.resume_position


@dataclass(frozen=True, slots=True)
class _Resume:
    char_offset: int
    chunk_index: int


@dataclass(frozen=True, slots=True)
class FakeVoiceRepo:
    def list_profiles(self):
        return [
            VoiceProfile(name="system", reference_audio_paths=[]),
            VoiceProfile(name="af_heart", reference_audio_paths=[]),
        ]


def test_play_when_idle_and_no_resume_prefers_first_section(monkeypatch, qapp) -> None:
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

    bookmarks_repo = FakeBookmarks(resume_position=None)
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=bookmarks_repo),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    calls: list[dict] = []
    narration.prepare = lambda **kwargs: calls.append(dict(kwargs))  # type: ignore[method-assign]

    class _B:
        def __init__(self, char_offset: int):
            self.char_offset = char_offset

    class _Comp:
        def __init__(self):
            self.bookmarks = [_B(123)]

    monkeypatch.setattr(
        "voice_reader.ui._ui_controller_playback.compute_structural_bookmarks",
        lambda _controller: _Comp(),
    )

    c.toggle_play_pause()

    assert len(calls) == 1
    assert calls[0]["start_char_offset"] == 123
    assert calls[0]["force_start_char"] == 123
    # Default behavior: resume persistence remains enabled.
    assert calls[0].get("persist_resume", True) is True


def test_play_when_idle_and_resume_exists_keeps_resume_path(monkeypatch, qapp) -> None:
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

    bookmarks_repo = FakeBookmarks(
        resume_position=_Resume(char_offset=1, chunk_index=7)
    )
    voice_service = VoiceProfileService(repo=FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=bookmarks_repo),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    prepare_calls: list[dict] = []
    narration.prepare = lambda **kwargs: prepare_calls.append(dict(kwargs))  # type: ignore[method-assign]

    touched = {"called": False}

    def _boom(_controller):
        touched["called"] = True
        raise AssertionError(
            "compute_structural_bookmarks should not run when resume exists"
        )

    monkeypatch.setattr(
        "voice_reader.ui._ui_controller_playback.compute_structural_bookmarks",
        _boom,
    )

    c.toggle_play_pause()

    assert len(prepare_calls) == 1
    assert prepare_calls[0].get("start_char_offset") is None
    assert prepare_calls[0].get("force_start_char") is None
    assert touched["called"] is False
