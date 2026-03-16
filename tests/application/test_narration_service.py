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
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository


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

    def alignment_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.base / book_id / voice_name / f"{chunk_id}.align.json"

    def alignment_exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        return (
            self.alignment_path(
                book_id=book_id, voice_name=voice_name, chunk_id=chunk_id
            )
            in self.existing
        )


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
class FakeKokoroEngine(FakeTTSEngine):
    @property
    def engine_name(self) -> str:
        return "kokoro"


@dataclass
class FakeStreamer(AudioStreamer):
    played: List[Path]
    pause_after_chunks: int | None = None
    pause_calls: int = 0
    _stop_flag: bool = False
    _pause_flag: bool = False
    rate: PlaybackRate = PlaybackRate.default()
    volume: PlaybackVolume = PlaybackVolume.default()

    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
        # Be resilient to a prior stop() call.
        # The real AudioStreamer should be reusable across multiple play sessions.
        self._stop_flag = False
        self._pause_flag = False
        it = iter(chunk_audio_paths)
        i = 0
        while not self._stop_flag:
            # When paused, stop consuming further paths (backpressure).
            while self._pause_flag and not self._stop_flag:
                return

            try:
                p = next(it)
            except StopIteration:
                return

            if on_chunk_start is not None:
                on_chunk_start(i)
            self.played.append(p)
            if on_playback_progress is not None:
                # Simulate a couple progress ticks within the chunk.
                on_playback_progress(i, 0)
                on_playback_progress(i, 120)
            if self.pause_after_chunks is not None and i + 1 >= self.pause_after_chunks:
                self.pause()
            if on_chunk_end is not None:
                on_chunk_end(i)
            i += 1

    def pause(self) -> None:
        self.pause_calls += 1
        self._pause_flag = True
        # Let NarrationService gate synthesis based on its pause event.
        try:
            owner = getattr(self, "_owner", None)
            if owner is not None and hasattr(owner, "pause"):
                owner.pause()
        except Exception:
            pass
        return

    def set_playback_rate(self, rate: PlaybackRate) -> None:
        self.rate = rate

    def set_volume(self, volume: PlaybackVolume) -> None:
        self.volume = volume

    def resume(self) -> None:
        self._pause_flag = False
        return

    def stop(self) -> None:
        self._stop_flag = True
        self._pause_flag = False
        return


@dataclass
class FakePreferences(PreferencesRepository):
    saved: list[PlaybackVolume]
    initial: PlaybackVolume | None = None

    def load_playback_volume(self) -> PlaybackVolume | None:
        return self.initial

    def save_playback_volume(self, volume: PlaybackVolume) -> None:
        self.saved.append(volume)


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


def test_prepare_can_restart_from_playback_index(tmp_path: Path) -> None:
    # Make enough text to produce multiple chunks.
    book = Book(
        id="b1",
        title="Test",
        raw_text="x",
        normalized_text=("A sentence. " * 200),
    )
    voice = VoiceProfile(name="v", reference_audio_paths=[tmp_path / "a.wav"])
    (tmp_path / "a.wav").write_bytes(b"x")

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeTTSEngine(calls=[])
    streamer = FakeStreamer(played=[])

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=60),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=0),
    )
    svc.load_book(tmp_path / "book.txt")
    chunks = svc.prepare(voice=voice)
    assert len(chunks) >= 3

    # Restart from the 2nd playback chunk.
    svc.prepare(voice=voice, start_playback_index=1)
    svc.start()
    assert svc.wait(timeout_seconds=5.0)
    # Should play fewer than full chunk count.
    assert len(streamer.played) < len(chunks)


def test_set_playback_rate_forwards_to_streamer(tmp_path: Path) -> None:
    book = Book(
        id="b1",
        title="Test",
        raw_text="Hello",
        normalized_text="Hello world.",
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

    svc.set_playback_rate(PlaybackRate(1.5))
    assert streamer.rate.multiplier == 1.5
    assert svc.playback_rate().multiplier == 1.5


def test_set_volume_forwards_to_streamer_without_restart(tmp_path: Path) -> None:
    book = Book(
        id="b1",
        title="Test",
        raw_text="Hello",
        normalized_text="Hello world.",
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

    # No playback thread should be started by a volume change.
    svc.set_volume(PlaybackVolume(0.5))
    assert streamer.volume.multiplier == 0.5
    assert svc.wait(timeout_seconds=0.01)


def test_volume_is_restored_and_persisted(tmp_path: Path) -> None:
    book = Book(
        id="b1",
        title="Test",
        raw_text="Hello",
        normalized_text="Hello world.",
    )
    voice = VoiceProfile(name="alice", reference_audio_paths=[tmp_path / "a.wav"])
    (tmp_path / "a.wav").write_bytes(b"x")

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeTTSEngine(calls=[])
    streamer = FakeStreamer(played=[])
    prefs = FakePreferences(saved=[], initial=PlaybackVolume(0.25))

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=40),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=0),
        preferences_repo=prefs,
    )
    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=voice)

    assert streamer.volume.multiplier == 0.25
    assert svc.playback_volume().multiplier == 0.25

    svc.set_volume(PlaybackVolume(0.8))
    assert prefs.saved
    assert prefs.saved[-1].multiplier == 0.8


def test_pause_stops_prefetch_beyond_current_chunk(tmp_path: Path) -> None:
    book = Book(
        id="b1",
        title="Test",
        raw_text="x",
        normalized_text=("A sentence. " * 300),
    )
    voice = VoiceProfile(name="v", reference_audio_paths=[tmp_path / "a.wav"])
    (tmp_path / "a.wav").write_bytes(b"x")

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeTTSEngine(calls=[])
    streamer = FakeStreamer(played=[], pause_after_chunks=1)

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=60),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=0),
    )
    # Wire back-reference so FakeStreamer.pause triggers svc.pause.
    streamer._owner = svc  # type: ignore[attr-defined]

    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=voice)
    svc.start()

    # Wait briefly for pause to engage.
    import time

    t0 = time.perf_counter()
    while streamer.pause_calls < 1 and (time.perf_counter() - t0) < 1.0:
        time.sleep(0.01)

    # Give synthesis a moment; it should not run away.
    calls_at_pause = len(engine.calls)
    time.sleep(0.2)
    calls_after = len(engine.calls)

    assert streamer.pause_calls >= 1
    assert calls_after == calls_at_pause

    # Highlight must not jump ahead to a future chunk during synthesis prefetch.
    # `current_chunk_id` is reserved for playback chunk index.
    assert svc.state.current_chunk_id in {0, None}

    # Stop so the narration thread terminates.
    svc.stop()
    assert svc.wait(timeout_seconds=5.0)


def test_parallel_kokoro_workers_can_be_enabled(monkeypatch, tmp_path: Path) -> None:
    # This test is intentionally light: it verifies that the code path doesn't
    # crash and still plays audio when the env var is enabled.
    monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "2")
    monkeypatch.setenv("NARRATEX_MAX_AHEAD_CHUNKS", "2")

    book = Book(
        id="b1",
        title="Test",
        raw_text="x",
        normalized_text=("A sentence. " * 50),
    )
    voice = VoiceProfile(name="v", reference_audio_paths=[])

    cache = FakeCache(base=tmp_path / "cache", existing=set())
    engine = FakeKokoroEngine(calls=[])
    streamer = FakeStreamer(played=[])

    svc = NarrationService(
        book_repo=FakeBookRepo(book=book),
        cache_repo=cache,
        tts_engine=engine,
        audio_streamer=streamer,
        chunking_service=ChunkingService(min_chars=10, max_chars=60),
        device="cpu",
        language="en",
        reading_start_detector=FixedStart(fixed_start_char=0),
    )

    svc.load_book(tmp_path / "book.txt")
    svc.prepare(voice=voice)
    svc.start()
    assert svc.wait(timeout_seconds=5.0)
    assert streamer.played


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
