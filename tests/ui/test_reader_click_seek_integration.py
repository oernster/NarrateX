from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


@dataclass
class _FakeNavChunkService:
    chunks: list[TextChunk]

    def build_chunks(self, *, book_text: str, skip_essay_index: bool = True):
        del book_text, skip_essay_index
        return list(self.chunks), None


@dataclass
class _FakeBookmarkRepo:
    saved: list[tuple[str, int, int]]

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
        self.saved.append((str(book_id), int(char_offset), int(chunk_index)))

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class _FakeVoiceRepo:
    def list_profiles(self):
        return [VoiceProfile(name="bf_emma", reference_audio_paths=[])]


@dataclass
class _FakeNarration:
    listeners: list
    prepare_calls: list
    stop_calls: list
    start_calls: int = 0

    # Needed by click-to-seek mapping.
    sanitized_text_mapper: SanitizedTextMapper = SanitizedTextMapper()

    def add_listener(self, listener):
        self.listeners.append(listener)

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return 0, 0

    def stop(self, *, persist_resume: bool = True):
        self.stop_calls.append(bool(persist_resume))

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
        del start_char_offset, force_start_char, skip_essay_index
        self.prepare_calls.append(
            {
                "voice": voice,
                "start_playback_index": start_playback_index,
                "persist_resume": persist_resume,
            }
        )

    def start(self):
        self.start_calls += 1

    def pause(self):
        return

    @property
    def chunking_service(self):
        # Present so UiController creates a navigation chunk service; tests override it.
        return object()


def test_click_to_seek_restarts_from_resolved_chunk_and_persists_resume(qapp) -> None:
    del qapp

    w = MainWindow()
    w.show()
    w.set_reader_text("x" * 200)

    narration = _FakeNarration(
        listeners=[],
        prepare_calls=[],
        stop_calls=[],
    )
    bm_repo = _FakeBookmarkRepo(saved=[])
    bookmark_service = BookmarkService(repo=bm_repo)  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        idea_map_service=None,
        idea_indexing_manager=None,
        structural_bookmark_service=None,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    # Force deterministic chunks and offsets.
    c._navigation_chunk_service = _FakeNavChunkService(  # noqa: SLF001
        chunks=[
            TextChunk(chunk_id=0, text="Alpha.", start_char=10, end_char=50),
            TextChunk(chunk_id=1, text="Beta.", start_char=50, end_char=90),
        ]
    )

    # Click somewhere in chunk 2.
    w.reader_seek_requested.emit(60)

    assert narration.stop_calls == [False]
    assert narration.start_calls == 1
    assert narration.prepare_calls
    assert narration.prepare_calls[-1]["start_playback_index"] == 1

    assert bm_repo.saved
    _book_id, char_off, chunk_idx = bm_repo.saved[-1]
    assert char_off == 50
    assert chunk_idx == 1


def test_click_to_seek_before_reading_start_is_clamped(qapp) -> None:
    del qapp

    w = MainWindow()
    w.show()
    w.set_reader_text("x" * 200)

    narration = _FakeNarration(
        listeners=[],
        prepare_calls=[],
        stop_calls=[],
    )
    bm_repo = _FakeBookmarkRepo(saved=[])
    bookmark_service = BookmarkService(repo=bm_repo)  # type: ignore[arg-type]
    voice_service = VoiceProfileService(repo=_FakeVoiceRepo())

    c = UiController(
        window=w,
        narration_service=narration,  # type: ignore[arg-type]
        bookmark_service=bookmark_service,
        idea_map_service=None,
        idea_indexing_manager=None,
        structural_bookmark_service=None,
        voice_service=voice_service,
        device="cpu",
        engine_name="engine",
        cover_extractor=None,
    )

    c._navigation_chunk_service = _FakeNavChunkService(  # noqa: SLF001
        chunks=[TextChunk(chunk_id=0, text="Alpha.", start_char=25, end_char=50)]
    )

    # Click before first narratable offset.
    w.reader_seek_requested.emit(0)

    assert narration.prepare_calls
    assert narration.prepare_calls[-1]["start_playback_index"] == 0
    assert bm_repo.saved
    _book_id, char_off, chunk_idx = bm_repo.saved[-1]
    assert char_off == 25
    assert chunk_idx == 0

    # UX hint (best-effort; may be overwritten quickly in real playback).
    assert "clamped" in (w.lbl_status.text() or "").lower()

