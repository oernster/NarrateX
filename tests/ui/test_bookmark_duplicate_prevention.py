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

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        # This location will be used for the duplicate check.
        return 12, 345


@dataclass
class _FakeBookmarkRepo:
    list_calls: int = 0
    add_calls: int = 0

    def list_bookmarks(self, *, book_id: str):
        self.list_calls += 1
        assert book_id == "b1"
        # Existing bookmark is in the same chunk_index, but with a different
        # char_offset. This must be considered a duplicate because Go To jumps
        # by chunk_index (chunk-level semantics).
        return [
            Bookmark(
                bookmark_id=1,
                name="Bookmark 1",
                char_offset=1,
                chunk_index=12,
                created_at=datetime(2026, 3, 14, 0, 0, 0, tzinfo=timezone.utc),
            )
        ]

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        self.add_calls += 1
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


def test_bookmark_add_is_noop_when_duplicate_position(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = _FakeNarration(listeners=[])
    repo = _FakeBookmarkRepo()
    bookmark_service = BookmarkService(repo=repo)  # type: ignore[arg-type]
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

    c.open_bookmarks_dialog()
    dlg = c._bookmarks_dialog  # noqa: SLF001
    assert dlg is not None

    # Trigger the add action; should *not* call repo.add_bookmark.
    dlg._actions.add_bookmark()  # noqa: SLF001

    assert repo.list_calls >= 1
    assert repo.add_calls == 0
