"""Application service orchestrating narration."""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from voice_reader.application.dto.narration_state import (
    NarrationState,
    NarrationStatus,
)
from voice_reader.domain.entities.book import Book
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.audio_streamer import AudioStreamer
from voice_reader.domain.interfaces.book_repository import BookRepository
from voice_reader.domain.interfaces.cache_repository import CacheRepository
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.domain.interfaces.reading_start_detector import ReadingStartDetector
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer

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
    reading_start_detector: ReadingStartDetector = ReadingStartService()
    spoken_text_sanitizer: SpokenTextSanitizer = SpokenTextSanitizer()

    def __post_init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._listeners: List[_StateListener] = []
        self._stop_event = threading.Event()
        self._play_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state = NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        )
        self._book: Book | None = None
        self._chunks: List[TextChunk] = []
        self._voice: VoiceProfile | None = None
        self._start_char: int | None = None
        self._cache_book_id: str | None = None

    @property
    def state(self) -> NarrationState:
        return self._state

    def add_listener(self, listener: _StateListener) -> None:
        self._listeners.append(listener)

    def load_book(self, source_path: Path) -> Book:
        self._set_state(
            NarrationState(
                status=NarrationStatus.LOADING,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Loading {source_path.name}...",
            )
        )
        book = self.book_repo.load(source_path)
        self._book = book
        self._start_char = None
        self._cache_book_id = None
        self._set_state(
            NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Loaded '{book.title}'",
            )
        )
        return book

    def prepare(self, *, voice: VoiceProfile) -> List[TextChunk]:
        if self._book is None:
            raise ValueError("Book not loaded")
        self._voice = voice

        start = self.reading_start_detector.detect_start(self._book.normalized_text)
        self._log.info("Narration start: %s at %s", start.reason, start.start_char)
        self._start_char = start.start_char
        self._cache_book_id = None

        self._set_state(
            NarrationState(
                status=NarrationStatus.CHUNKING,
                current_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Chunking text ({start.reason})...",
            )
        )

        slice_text = self._book.normalized_text[start.start_char :]
        sliced_chunks = self.chunking_service.chunk_text(slice_text)
        # Re-base chunk coordinates to full-book coordinates.
        self._chunks = [
            TextChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                start_char=c.start_char + start.start_char,
                end_char=c.end_char + start.start_char,
            )
            for c in sliced_chunks
        ]
        self._set_state(
            NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                total_chunks=len(self._chunks),
                progress=0.0,
                message=f"Prepared {len(self._chunks)} chunks",
            )
        )
        return list(self._chunks)

    def start(self) -> None:
        with self._lock:
            if self._play_thread and self._play_thread.is_alive():
                return
            if self._book is None or self._voice is None:
                raise ValueError("Book and voice must be set before start")
            if not self._chunks:
                self._chunks = self.chunking_service.chunk_text(
                    self._book.normalized_text
                )
            self._stop_event.clear()
            self._play_thread = threading.Thread(
                target=self._run,
                name="narration-thread",
                daemon=True,
            )
            self._play_thread.start()

    def wait(self, timeout_seconds: float | None = None) -> bool:
        """Wait for the current narration thread to finish.

        This is primarily intended for deterministic unit tests.

        Returns True if the thread finished within the timeout.
        """

        t = self._play_thread
        if t is None:
            return True
        t.join(timeout=timeout_seconds)
        return not t.is_alive()

    def pause(self) -> None:
        # Pause should also prevent playback from starting if we're still
        # synthesizing/caching.
        self.audio_streamer.pause()
        self._set_state(
            NarrationState(
                status=NarrationStatus.PAUSED,
                current_chunk_id=self._state.current_chunk_id,
                total_chunks=self._state.total_chunks,
                progress=self._state.progress,
                message="Paused",
                highlight_start=self._state.highlight_start,
                highlight_end=self._state.highlight_end,
            )
        )

    def resume(self) -> None:
        # Resume means: restart the current chunk from the beginning.
        # The AudioStreamer implementation handles the chunk replay semantics.
        self.audio_streamer.resume()
        self._set_state(
            NarrationState(
                status=NarrationStatus.PLAYING,
                current_chunk_id=self._state.current_chunk_id,
                total_chunks=self._state.total_chunks,
                progress=self._state.progress,
                message="Playing",
                highlight_start=self._state.highlight_start,
                highlight_end=self._state.highlight_end,
            )
        )

    def stop(self) -> None:
        self._stop_event.set()
        self.audio_streamer.stop()

        # Ensure the narration thread has terminated so a subsequent start() is
        # not ignored due to an "already alive" thread.
        self.wait(timeout_seconds=2.0)

        self._set_state(
            NarrationState(
                status=NarrationStatus.STOPPED,
                current_chunk_id=None,
                total_chunks=self._state.total_chunks,
                progress=0.0,
                message="Stopped",
                highlight_start=None,
                highlight_end=None,
            )
        )

    def book_id(self) -> str:
        if self._book is None:
            raise ValueError("Book not loaded")
        # Stable hash to key cache.
        # IMPORTANT: include the detected start offset and a version tag so we
        # don't reuse old chunk0 audio after changing front-matter skipping or
        # spoken-text sanitization.
        if self._cache_book_id is not None:
            return self._cache_book_id

        if self._start_char is None:
            start = self.reading_start_detector.detect_start(self._book.normalized_text)
            self._start_char = start.start_char

        version_tag = "v3"
        payload = f"{self._book.normalized_text}|start={self._start_char}|{version_tag}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._cache_book_id = digest[:16]
        return self._cache_book_id

    def _run(self) -> None:
        assert self._book is not None
        assert self._voice is not None
        book_id = self.book_id()
        total = len(self._chunks)

        audio_paths: List[Path] = []
        playback_chunks: List[TextChunk] = []
        try:
            for chunk in self._chunks:
                if self._stop_event.is_set():
                    return
                self._set_state(
                    NarrationState(
                        status=NarrationStatus.SYNTHESIZING,
                        current_chunk_id=chunk.chunk_id,
                        total_chunks=total,
                        progress=chunk.chunk_id / max(total, 1),
                        message=f"Preparing chunk {chunk.chunk_id + 1}/{total}",
                        highlight_start=chunk.start_char,
                        highlight_end=chunk.end_char,
                    )
                )

                path = self.cache_repo.audio_path(
                    book_id=book_id,
                    voice_name=self._voice.name,
                    chunk_id=chunk.chunk_id,
                )
                speak_text = self.spoken_text_sanitizer.sanitize(chunk.text)
                if not speak_text:
                    # If the chunk contains only numbering, skip playback.
                    continue

                if not self.cache_repo.exists(
                    book_id=book_id,
                    voice_name=self._voice.name,
                    chunk_id=chunk.chunk_id,
                ):
                    self.cache_repo.ensure_parent_dir(path)
                    self.tts_engine.synthesize_to_file(
                        text=speak_text,
                        voice_profile=self._voice,
                        output_path=path,
                        device=self.device,
                        language=self.language,
                    )
                audio_paths.append(path)
                playback_chunks.append(chunk)

            playback_total = len(playback_chunks)

            def on_start(play_index: int) -> None:
                if play_index < 0 or play_index >= playback_total:
                    return
                c = playback_chunks[play_index]
                self._set_state(
                    NarrationState(
                        status=NarrationStatus.PLAYING,
                        current_chunk_id=play_index,
                        total_chunks=playback_total,
                        progress=play_index / max(playback_total, 1),
                        message=f"Playing chunk {play_index + 1}/{playback_total}",
                        highlight_start=c.start_char,
                        highlight_end=c.end_char,
                    )
                )

            self.audio_streamer.start(
                chunk_audio_paths=audio_paths,
                on_chunk_start=on_start,
                on_chunk_end=None,
            )

            self._set_state(
                NarrationState(
                    status=NarrationStatus.IDLE,
                    current_chunk_id=None,
                    total_chunks=playback_total,
                    progress=1.0,
                    message="Done",
                )
            )
        except Exception as exc:  # pragma: no cover
            self._log.exception("Narration failed")
            self._set_state(
                NarrationState(
                    status=NarrationStatus.ERROR,
                    current_chunk_id=self._state.current_chunk_id,
                    total_chunks=self._state.total_chunks,
                    progress=self._state.progress,
                    message=str(exc),
                )
            )

    def _set_state(self, state: NarrationState) -> None:
        self._state = state
        for listener in list(self._listeners):
            try:
                listener(state)
            except Exception:  # pragma: no cover
                self._log.exception("Listener failed")
