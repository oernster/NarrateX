from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.audio_streamer import AudioStreamer
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.domain.interfaces.cache_repository import CacheRepository
from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.domain.services.reading_start_service import ReadingStart
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


@dataclass(frozen=True, slots=True)
class FakeBookRepo(BookRepository):
    book: Book

    def load(self, source_path: Path) -> Book:
        del source_path
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
        del voice_profile, device, language
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

    def set_playback_rate(self, rate: PlaybackRate) -> None:
        self.rate = rate

    def set_volume(self, volume: PlaybackVolume) -> None:
        self.volume = volume

    def resume(self) -> None:
        self._pause_flag = False

    def stop(self) -> None:
        self._stop_flag = True
        self._pause_flag = False


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
