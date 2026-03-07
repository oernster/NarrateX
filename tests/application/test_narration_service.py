from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from voice_reader.application.services.narration_service import NarrationService
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.audio_streamer import AudioStreamer
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.domain.interfaces.cache_repository import CacheRepository
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStart


@dataclass(frozen=True, slots=True)
class FakeBookRepo(BookRepository):
    book: Book

    def load(self, source_path: Path) -> Book:
        return self.book


@dataclass
class FakeCache(CacheRepository):
    base: Path
    existing: set[Path]

    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.wav"

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        return (
            self.audio_path(book_id=book_id, voice_name=voice_name, chunk_id=chunk_id)
            in self.existing
        )

    def ensure_parent_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class FakeTTSEngine(TTSEngine):
    calls: List[str]

    @property
    def engine_name(self) -> str:
        return "Fake"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        self.calls.append(text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF....WAVE")
        return output_path


@dataclass
class FakeStreamer(AudioStreamer):
    played: List[Path]

    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start=None,
        on_chunk_end=None,
    ) -> None:
        for i, p in enumerate(chunk_audio_paths):
            if on_chunk_start is not None:
                on_chunk_start(i)
            self.played.append(p)
            if on_chunk_end is not None:
                on_chunk_end(i)

    def pause(self) -> None:
        return

    def resume(self) -> None:
        return

    def stop(self) -> None:
        return


class FixedStart:
    def __init__(self, fixed_start_char: int) -> None:
        self.fixed_start_char = fixed_start_char

    def detect_start(self, text: str) -> ReadingStart:
        del text
        return ReadingStart(start_char=self.fixed_start_char, reason="Fixed")


def test_narration_uses_cache_before_synthesis(tmp_path: Path) -> None:
    book = Book(
        id="b1",
        title="Test",
        raw_text="Hello world.",
        normalized_text="Hello world. " * 20,
    )
    voice = VoiceProfile(name="alice", reference_audio_paths=[tmp_path / "a.wav"])
    (tmp_path / "a.wav").write_bytes(b"x")

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeTTSEngine(calls=[])
    streamer = FakeStreamer(played=[])

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=40),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=0),
    )
    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=voice)
    # Pre-populate cache for first chunk only.
    book_id = svc.book_id()
    first = cache.audio_path(book_id=book_id, voice_name=voice.name, chunk_id=0)
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_bytes(b"cached")
    cache.existing.add(first)

    svc.start()
    assert svc.wait(timeout_seconds=2.0)
    # Fake streamer plays all chunks.
    assert streamer.played
    # Engine should have been called for chunks except cached ones.
    assert len(engine.calls) == max(len(streamer.played) - 1, 0)


def test_narration_skips_front_matter_by_start_offset(tmp_path: Path) -> None:
    # Front matter + Chapter 1 marker.
    text = "Title\n\nContents\nChapter 1 .... 1\n\nCHAPTER 1\nHello. " * 5
    book = Book(id="b1", title="Test", raw_text=text, normalized_text=text)
    voice = VoiceProfile(name="system", reference_audio_paths=[tmp_path / "a.wav"])
    (tmp_path / "a.wav").write_bytes(b"x")

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeTTSEngine(calls=[])
    streamer = FakeStreamer(played=[])

    # Force start at the CHAPTER 1 marker.
    start_idx = text.find("CHAPTER 1")
    assert start_idx > 0

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=80),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=start_idx),
    )
    svc.load_book(tmp_path / "book.txt")
    chunks = svc.prepare(voice=voice)
    assert chunks
    assert chunks[0].start_char >= start_idx
