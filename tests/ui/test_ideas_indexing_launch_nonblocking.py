from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


@dataclass
class _FakeNarration:
    listeners: list
    state: NarrationState
    prepare_calls: int = 0
    start_calls: int = 0

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def prepare(self, *, voice, start_playback_index=None):
        del voice, start_playback_index
        self.prepare_calls += 1

    def start(self):
        self.start_calls += 1


@dataclass
class _FakeBookmarks:
    def list_bookmarks(self, *, book_id: str):
        del book_id
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        del book_id, bookmark_id

    def save_resume_position(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


def test_start_ideas_indexing_is_nonblocking_and_play_can_run_immediately(qapp, monkeypatch):
    """Regression: requesting mapping must not block Play.

    This test proves the UI-facing method doesn't synchronously call the manager.
    """

    del qapp
    w = MainWindow()

    narration = _FakeNarration(
        listeners=[],
        state=NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        ),
    )
    # Provide a book object so launcher can snapshot normalized_text.
    narration._book = type("B", (), {"normalized_text": "X" * 10, "title": "T"})()  # type: ignore[attr-defined]

    class _Mgr:
        def __init__(self):
            self.start_calls = 0

        def start_indexing(self, **kwargs):
            del kwargs
            self.start_calls += 1

        def poll(self, *, book_id: str):
            del book_id
            return []

    mgr = _Mgr()

    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    # Patch Thread.start so the launcher doesn't run during this test.
    import threading

    original_start = threading.Thread.start
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=BookmarkService(repo=_FakeBookmarks()),  # type: ignore[arg-type]
        idea_map_service=None,
        idea_indexing_manager=mgr,  # type: ignore[arg-type]
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Should return without synchronously spawning/starting the manager.
    c._start_ideas_indexing(book_id="b1")  # noqa: SLF001
    assert mgr.start_calls == 0

    # Playback should still be callable immediately.
    c.play()
    assert narration.prepare_calls == 1
    assert narration.start_calls == 1

    # Restore for safety (even though monkeypatch would revert).
    monkeypatch.setattr(threading.Thread, "start", original_start)

