"""Application service orchestrating narration.

This file intentionally holds only the public façade:
`NarrationService` and its public API. Heavy logic is split into
`voice_reader.application.services.narration.*` so every module stays <=400 LOC.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from voice_reader.application.dto.narration_state import NarrationState
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.application.services.narration.cache_key import compute_book_cache_id
from voice_reader.application.services.narration.persistence import (
    maybe_save_resume_position,
)
from voice_reader.application.services.narration.book_loading import (
    load_book as _load_book,
)
from voice_reader.application.services.narration.control import (
    on_app_exit as _on_app_exit,
    pause as _pause,
    request_stop_after_current_chunk as _request_stop_after_current_chunk,
    resume as _resume,
    start as _start,
    stop as _stop,
    wait as _wait,
)
from voice_reader.application.services.narration.init import init_runtime_state
from voice_reader.application.services.narration.position import (
    current_position as _current_position,
)
from voice_reader.application.services.narration.prepare import (
    prepare as _prepare,
    resolve_playback_index_for_char_offset as _resolve_playback_index_for_char_offset,
)
from voice_reader.application.services.narration.run import run as _run
from voice_reader.application.services.playback_synchronizer import PlaybackSynchronizer
from voice_reader.domain.alignment.alignment_io import AlignmentIO
from voice_reader.domain.alignment.estimated_aligner import EstimatedAligner
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.audio_streamer import AudioStreamer
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.domain.interfaces.cache_repository import CacheRepository
from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository
from voice_reader.domain.interfaces.reading_start_detector import ReadingStartDetector
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.application.services.narration.init import (
    default_reading_start_detector,
)
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper
from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

_StateListener = Callable[[NarrationState], None]


@dataclass
class NarrationService:
    book_repo: BookRepository
    cache_repo: CacheRepository
    tts_engine: TTSEngine
    audio_streamer: AudioStreamer
    chunking_service: ChunkingService
    device: str
    language: str
    reading_start_detector: ReadingStartDetector = default_reading_start_detector()
    spoken_text_sanitizer: SpokenTextSanitizer = SpokenTextSanitizer()
    sanitized_text_mapper: SanitizedTextMapper = SanitizedTextMapper()

    navigation_chunk_service: NavigationChunkService | None = None

    playback_synchronizer: PlaybackSynchronizer = PlaybackSynchronizer()
    alignment_io: AlignmentIO = AlignmentIO()
    estimated_aligner: EstimatedAligner = EstimatedAligner()

    # Optional: resume persistence (manual bookmarks are handled by UI/BookmarkService).
    bookmark_service: BookmarkService | None = None

    # Optional: lightweight user preferences persistence.
    preferences_repo: PreferencesRepository | None = None

    def __post_init__(self) -> None:
        init_runtime_state(self)

    def set_playback_rate(self, rate: PlaybackRate) -> None:
        self._playback_rate = rate
        self.audio_streamer.set_playback_rate(rate)

    def set_volume(self, volume: PlaybackVolume) -> None:
        """Set playback volume for the current session.

        This is a playback-layer concern only. It must not restart narration,
        invalidate chunk state, or influence TTS caching.
        """

        self._volume = volume
        self.audio_streamer.set_volume(volume)

        if self.preferences_repo is not None:
            try:
                self.preferences_repo.save_playback_volume(volume)
            except Exception:
                self._log.exception("Failed saving playback volume")

    def playback_volume(self) -> PlaybackVolume:
        return self._volume

    def playback_rate(self) -> PlaybackRate:
        return self._playback_rate

    @property
    def state(self) -> NarrationState:
        return self._state

    def add_listener(self, listener: _StateListener) -> None:
        self._listeners.append(listener)

    def load_book(self, source_path: Path) -> Book:
        return _load_book(self, source_path)

    def loaded_book_id(self) -> str | None:
        """Return the current domain book id for bookmark storage."""

        return None if self._book is None else self._book.id

    def current_position(self) -> tuple[int | None, int | None]:
        return _current_position(self)

    def _maybe_save_resume_position(self) -> None:
        maybe_save_resume_position(self)

    def prepare(
        self,
        *,
        voice: VoiceProfile,
        start_playback_index: int | None = None,
        start_char_offset: int | None = None,
        force_start_char: int | None = None,
        skip_essay_index: bool = True,
        persist_resume: bool = True,
    ) -> list[TextChunk]:
        return _prepare(
            self,
            voice=voice,
            start_playback_index=start_playback_index,
            start_char_offset=start_char_offset,
            force_start_char=force_start_char,
            skip_essay_index=skip_essay_index,
            persist_resume=persist_resume,
        )

    def _resolve_playback_index_for_char_offset(
        self, *, char_offset: int, chunks: list[TextChunk]
    ) -> int | None:
        return _resolve_playback_index_for_char_offset(
            self,
            char_offset=int(char_offset),
            chunks=list(chunks),
        )

    def start(self) -> None:
        _start(self)

    def request_stop_after_current_chunk(self) -> None:
        _request_stop_after_current_chunk(self)

    def wait(self, timeout_seconds: float | None = None) -> bool:
        return _wait(self, timeout_seconds=timeout_seconds)

    def pause(self) -> None:
        _pause(self)

    def resume(self) -> None:
        _resume(self)

    def stop(self, *, persist_resume: bool = True) -> None:
        _stop(self, persist_resume=bool(persist_resume))

    def on_app_exit(self) -> None:
        _on_app_exit(self)

    def book_id(self) -> str:
        return compute_book_cache_id(self)

    def _run(self) -> None:
        _run(self)

    def _set_state(self, state: NarrationState) -> None:
        self._state = state
        for listener in list(self._listeners):
            try:
                listener(state)
            except Exception:  # pragma: no cover
                self._log.exception("Listener failed")
