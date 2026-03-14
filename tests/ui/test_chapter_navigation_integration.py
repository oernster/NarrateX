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
    prepare_calls: list
    start_calls: int = 0
    stop_calls: int = 0
    current_pos: tuple[int | None, int | None] = (0, 0)

    # These are used by UiController to build navigation chunks.
    reading_start_detector: object | None = None
    chunking_service: object | None = None

    state: NarrationState = NarrationState(
        status=NarrationStatus.IDLE,
        current_chunk_id=None,
        total_chunks=None,
        progress=0.0,
        message="Idle",
    )

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return self.current_pos

    def prepare(self, *, voice, start_playback_index=None):
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

    def save_resume_position(self, *, book_id: str, char_offset: int, chunk_index: int) -> None:
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


def test_chapter_controls_disabled_when_no_chapters(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = _FakeNarration(listeners=[], prepare_calls=[])
    bookmark_service = BookmarkService(repo=_FakeBookmarkRepo())  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())
    UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    assert w.btn_prev_chapter.isEnabled() is False
    assert w.btn_next_chapter.isEnabled() is False


def test_prev_next_chapter_jump_uses_prepare_with_target_chunk_index(qapp, monkeypatch) -> None:
    del qapp
    del monkeypatch
    w = MainWindow()
    narration = _FakeNarration(listeners=[], prepare_calls=[])
    bookmark_service = BookmarkService(repo=_FakeBookmarkRepo())  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    # Inject a deterministic chapter list and force current position.
    from voice_reader.domain.entities.chapter import Chapter

    c._chapters = [  # noqa: SLF001
        Chapter(title="Chapter 1", char_offset=0, chunk_index=0),
        Chapter(title="Chapter 2", char_offset=100, chunk_index=5),
        Chapter(title="Chapter 3", char_offset=200, chunk_index=9),
    ]

    # Simulate being in the middle (char_offset between chapter 2 and 3).
    narration.current_pos = (5, 150)

    # Next chapter should jump to chapter 3 chunk_index=9.
    c.next_chapter()
    assert narration.stop_calls == 1
    assert narration.start_calls == 1
    _voice, idx = narration.prepare_calls[-1]
    assert idx == 9

    # Previous chapter from the same position should jump to chapter 2 chunk_index=5.
    narration.current_pos = (9, 150)
    c.previous_chapter()
    _voice, idx = narration.prepare_calls[-1]
    # When inside Chapter 2, "previous" goes to Chapter 1.
    assert idx == 0


def test_prev_next_chapter_boundaries_noop(qapp) -> None:
    del qapp
    w = MainWindow()
    narration = _FakeNarration(listeners=[], prepare_calls=[])
    bookmark_service = BookmarkService(repo=_FakeBookmarkRepo())  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())
    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
    )

    from voice_reader.domain.entities.chapter import Chapter

    c._chapters = [  # noqa: SLF001
        Chapter(title="Chapter 1", char_offset=0, chunk_index=0),
        Chapter(title="Chapter 2", char_offset=100, chunk_index=5),
    ]

    # At first chapter -> previous is noop.
    narration.current_pos = (0, 0)
    c.previous_chapter()
    assert narration.prepare_calls == []

    # At last chapter -> next is noop.
    narration.current_pos = (5, 200)
    c.next_chapter()
    assert narration.prepare_calls == []

