from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.idea_map_service import IdeaMapService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.bookmark import Bookmark
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController

from tests.ui._fakes_ideas_repo import FakeIdeasRepo


@dataclass
class _FakeNarration:
    listeners: list
    prepare_calls: list
    start_calls: int = 0
    stop_calls: int = 0

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return 0, 0

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
        del start_char_offset, force_start_char, skip_essay_index, persist_resume
        self.prepare_calls.append((voice, start_playback_index))

    def start(self):
        self.start_calls += 1

    def pause(self):
        return

    def stop(self):
        self.stop_calls += 1


@dataclass
class _FakeBookmarkRepo:
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
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


def test_go_to_bookmark_calls_prepare_with_chunk_index_and_starts(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = _FakeNarration(listeners=[], prepare_calls=[])
    bookmark_service = BookmarkService(repo=_FakeBookmarkRepo())  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        idea_map_service=IdeaMapService(repo=FakeIdeasRepo()),  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    bm = Bookmark(
        bookmark_id=1,
        name="Bookmark 1",
        char_offset=10,
        chunk_index=12,
        created_at=datetime.now(timezone.utc),
    )

    # Create the dialog and trigger the go-to action.
    c.open_bookmarks_dialog()
    dlg = c._bookmarks_dialog  # noqa: SLF001
    assert dlg is not None
    assert dlg.isVisible() is True
    dlg._actions.go_to_bookmark(bm)  # noqa: SLF001

    # Requirement: Go To closes the dialog.
    assert dlg.isVisible() is False

    assert narration.stop_calls == 1
    assert narration.start_calls == 1
    assert narration.prepare_calls
    _voice, idx = narration.prepare_calls[-1]
    assert idx == 12
