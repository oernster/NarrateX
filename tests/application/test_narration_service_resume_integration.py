from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        del text, voice_profile, device, language
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF....WAVE")
        return output_path


@dataclass
class _FakeStreamer:
    def set_playback_rate(self, rate) -> None:
        del rate

    def start(
        self,
        *,
        chunk_audio_paths,
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
        del chunk_audio_paths, on_chunk_start, on_chunk_end, on_playback_progress

    def pause(self) -> None:
        return

    def resume(self) -> None:
        return

    def stop(self) -> None:
        return


@dataclass
class _FakeBookmarkService:
    resume_chunk_index: int | None
    load_calls: int = 0

    def load_resume_position(self, *, book_id: str):
        self.load_calls += 1
        assert book_id == "book-1"
        if self.resume_chunk_index is None:
            return None
        # ResumePosition is a domain object; NarrationService only needs chunk_index.
        return type(
            "RP",
            (),
            {
                "chunk_index": int(self.resume_chunk_index),
                "char_offset": 0,
                "updated_at": None,
            },
        )()

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        del book_id, char_offset, chunk_index


def test_prepare_uses_resume_position_when_present(tmp_path: Path) -> None:
    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello world")
    svc = NarrationService(
        book_repo=_FakeBookRepo(book=book),  # type: ignore[arg-type]
        cache_repo=_FakeCache(base=tmp_path),  # type: ignore[arg-type]
        tts_engine=_FakeTTSEngine(),  # type: ignore[arg-type]
        audio_streamer=_FakeStreamer(),  # type: ignore[arg-type]
        chunking_service=ChunkingService(min_chars=1, max_chars=5),
        device="cpu",
        language="en",
        bookmark_service=_FakeBookmarkService(
            resume_chunk_index=7
        ),  # type: ignore[arg-type]
    )
    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=VoiceProfile(name="v", reference_audio_paths=[]))
    # Uses resume chunk index as the start playback index.
    assert svc._start_playback_index == 7  # noqa: SLF001


def test_prepare_starts_from_beginning_when_no_resume(tmp_path: Path) -> None:
    book = Book(id="book-1", title="T", raw_text="x", normalized_text="Hello world")
    bs = _FakeBookmarkService(resume_chunk_index=None)
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
    svc.prepare(voice=VoiceProfile(name="v", reference_audio_paths=[]))
    assert svc._start_playback_index == 0  # noqa: SLF001
    assert bs.load_calls == 1
