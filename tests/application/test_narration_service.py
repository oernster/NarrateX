from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.narration_service import NarrationService
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume
from tests.application.narration_service_fakes import (
    FakeBookRepo,
    FakeCache,
    FakeKokoroEngine,
    FakePreferences,
    FakeStreamer,
    FakeTTSEngine,
    FixedStart,
)


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
