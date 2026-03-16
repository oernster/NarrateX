from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.chunking_service import ChunkingService


@dataclass(frozen=True, slots=True)
class _FakeBookRepo:
    book: Book

    def load(self, source_path: Path) -> Book:
        del source_path
        return self.book


@dataclass
class _FakeCache:
    base: Path

    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.wav"

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        del book_id, voice_name, chunk_id
        return False

    def ensure_parent_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def alignment_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.align.json"

    def alignment_exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        del book_id, voice_name, chunk_id
        return False


@dataclass
class _FakeTTSEngine:
    @property
    def engine_name(self) -> str:
        return "fake"


@dataclass
class _FakeStreamer:
    def set_playback_rate(self, rate) -> None:
        del rate

    def set_volume(self, volume) -> None:
        del volume

    def start(self, *, chunk_audio_paths, **_kwargs) -> None:
        del chunk_audio_paths

    def wait(self, timeout_seconds: float | None = None) -> bool:
        del timeout_seconds
        return True

    def pause(self) -> None:
        return

    def resume(self) -> None:
        return

    def stop(self) -> None:
        return


@dataclass
class _FakeBookmarkService:
    save_calls: int = 0
    last_saved: tuple[str, int, int] | None = None

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None

    def save_resume_position(self, *, book_id: str, char_offset: int, chunk_index: int):
        self.save_calls += 1
        self.last_saved = (str(book_id), int(char_offset), int(chunk_index))


def test_prepare_start_char_offset_maps_to_playback_candidate_index(tmp_path: Path) -> None:
    # Arrange: a "number-only" chunk should be filtered out of playback candidates,
    # so mapping needs to consider speak_text filtering.
    text = "1\n\nAlpha beta.\n\nGamma delta."
    book = Book(id="book-1", title="T", raw_text=text, normalized_text=text)

    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5000),
        device="cpu",
        language="en",
        bookmark_service=_FakeBookmarkService(),  # type: ignore[arg-type]
    )
    svc.load_book(tmp_path / "book.txt")

    # Act: request a jump into the second paragraph (Gamma...) by absolute char offset.
    off = int(text.index("Gamma"))
    svc.prepare(
        voice=VoiceProfile(name="v", reference_audio_paths=[]),
        start_char_offset=off,
        force_start_char=0,
        skip_essay_index=False,
        persist_resume=False,
    )

    # Assert: first candidate is "Alpha..." (chunk 1). Second candidate is "Gamma...".
    # The number-only chunk is not a candidate.
    assert svc._start_playback_index == 1  # noqa: SLF001


def test_prepare_persist_resume_false_suppresses_resume_saves(tmp_path: Path) -> None:
    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello world")
    bs = _FakeBookmarkService()
    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=bs,  # type: ignore[arg-type]
    )
    svc.load_book(tmp_path / "book.txt")

    # Simulate we're playing at a known position.
    svc._set_state(
        NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=0,
            total_chunks=1,
            progress=0.0,
            audible_start=123,
        )
    )

    svc.prepare(
        voice=VoiceProfile(name="v", reference_audio_paths=[]),
        start_playback_index=0,
        persist_resume=False,
    )

    # Stop should not save because persistence is suppressed.
    svc.stop()
    assert bs.save_calls == 0

