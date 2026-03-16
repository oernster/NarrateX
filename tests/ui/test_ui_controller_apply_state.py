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

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return None, None


@dataclass
class FakeBookmarks:
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
        return None


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
        bookmark_service=BookmarkService(repo=FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo()),  # type: ignore[arg-type]
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

    # Select Book must be locked (disabled + orange border property) during playback.
    assert w.btn_select_book.isEnabled() is False
    assert w.btn_select_book.property("selectBookLocked") is True

    # Unlock on paused.
    c._apply_state(
        NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=0,
            total_chunks=10,
            progress=0.5,
            message="Paused",
            highlight_start=0,
            highlight_end=3,
        )
    )
    assert w.btn_select_book.isEnabled() is True
    assert w.btn_select_book.property("selectBookLocked") is False

    # Lock for other active statuses.
    for status in (
        NarrationStatus.LOADING,
        NarrationStatus.CHUNKING,
        NarrationStatus.SYNTHESIZING,
    ):
        c._apply_state(
            NarrationState(
                status=status,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message="",
            )
        )
        assert w.btn_select_book.isEnabled() is False
        assert w.btn_select_book.property("selectBookLocked") is True

    # Ensure it remains enabled for stopped/idle/error.
    for status in (
        NarrationStatus.STOPPED,
        NarrationStatus.IDLE,
        NarrationStatus.ERROR,
    ):
        c._apply_state(
            NarrationState(
                status=status,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message="",
            )
        )
        assert w.btn_select_book.isEnabled() is True
        assert w.btn_select_book.property("selectBookLocked") is False
