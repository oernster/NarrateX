"""Application service orchestrating narration."""

from __future__ import annotations

import hashlib
import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import os

from voice_reader.application.services.playback_synchronizer import PlaybackSynchronizer
from voice_reader.domain.alignment.alignment_io import AlignmentIO
from voice_reader.domain.alignment.estimated_aligner import EstimatedAligner
from voice_reader.domain.alignment.model import ChunkAlignment

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
from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper
from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer

from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)

from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

from voice_reader.application.services.bookmark_service import BookmarkService

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
        self._log = logging.getLogger(self.__class__.__name__)
        self._listeners: List[_StateListener] = []
        self._stop_event = threading.Event()
        # Allows a graceful stop at the next chunk boundary (end of current chunk).
        # Used by queued navigation actions (e.g. Ideas Go To) to avoid cutting audio
        # mid-chunk.
        self._stop_after_current_chunk = threading.Event()
        self._play_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state = NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=None,
            progress=0.0,
        )
        self._book: Book | None = None
        self._chunks: List[TextChunk] = []
        self._voice: VoiceProfile | None = None
        self._start_char: int | None = None
        self._cache_book_id: str | None = None
        # Pause state used to gate synthesis prefetch.
        self._pause_event = threading.Event()
        # Tracks the currently playing chunk index (playback index, not chunk_id).
        self._current_play_index: int = -1
        # Allows restarting narration from a given playback index.
        self._start_playback_index: int = 0
        self._playback_rate: PlaybackRate = PlaybackRate.default()
        self._volume: PlaybackVolume = PlaybackVolume.default()

        # When False, suppress resume persistence while this run is active.
        # Used by Ideas "Go To" jumps so they don't overwrite the user's resume.
        self._persist_resume: bool = True

        # Restore persisted volume (best-effort). Playback concern only.
        if self.preferences_repo is not None:
            try:
                restored = self.preferences_repo.load_playback_volume()
            except Exception:
                restored = None
            if restored is not None:
                self._volume = restored

        if self.navigation_chunk_service is None:
            self.navigation_chunk_service = NavigationChunkService(
                reading_start_detector=self.reading_start_detector,
                chunking_service=self.chunking_service,
            )

        # Ensure the playback layer is initialized with our default rate.
        # This is a playback concern only; it must not affect cache/TTS.
        try:
            self.audio_streamer.set_playback_rate(self._playback_rate)
        except Exception:
            # Audio streamer may be a stub in tests.
            pass

        # Initialize default volume (session-only).
        try:
            self.audio_streamer.set_volume(self._volume)
        except Exception:
            pass

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
        # Book switch: persist resume for the previous book (best-effort).
        self._maybe_save_resume_position()

        # Reset persistence policy to default for the new book/session.
        # Idea-map "Go To" jumps temporarily disable resume persistence.
        self._persist_resume = True

        # If a playback thread is active (e.g. user paused but did not stop),
        # stop it before switching books. Otherwise `start()` can no-op due to the
        # previous thread still being alive.
        try:
            self.stop()
        except Exception:
            # Best-effort: book switching should still proceed even if stop fails.
            pass
        self._set_state(
            NarrationState(
                status=NarrationStatus.LOADING,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=None,
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
                playback_chunk_id=None,
                prefetch_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Loaded '{book.title}'",
            )
        )
        return book

    def loaded_book_id(self) -> str | None:
        """Return the current domain book id for bookmark storage."""

        return None if self._book is None else self._book.id

    def current_position(self) -> tuple[int | None, int | None]:
        """Return (chunk_index, char_offset) for the current playback position.

        chunk_index is the *absolute playback index* into the candidate list used by
        [`prepare()`](voice_reader/application/services/narration_service.py:138).
        """

        st = self._state

        rel_idx = st.playback_chunk_id
        if rel_idx is None:
            rel_idx = st.current_chunk_id

        if rel_idx is None:
            return None, None

        chunk_index = int(self._start_playback_index) + int(rel_idx)

        char_offset = st.audible_start
        if char_offset is None:
            char_offset = st.highlight_start

        if char_offset is None:
            # Last resort: map to a chunk start. This may be approximate because the
            # playback candidate list can skip empty spoken chunks.
            try:
                char_offset = int(self._chunks[int(chunk_index)].start_char)
            except Exception:
                char_offset = None

        return chunk_index, char_offset

    def _maybe_save_resume_position(self) -> None:
        if not bool(getattr(self, "_persist_resume", True)):
            return
        if self.bookmark_service is None:
            return
        if self._book is None:
            return
        chunk_index, char_offset = self.current_position()
        if chunk_index is None or char_offset is None:
            return
        try:
            self.bookmark_service.save_resume_position(
                book_id=self._book.id,
                char_offset=int(char_offset),
                chunk_index=int(chunk_index),
            )
        except Exception:
            # Resume persistence must never break playback.
            self._log.exception("Failed saving resume position")

    def prepare(
        self,
        *,
        voice: VoiceProfile,
        start_playback_index: int | None = None,
        start_char_offset: int | None = None,
        force_start_char: int | None = None,
        skip_essay_index: bool = True,
        persist_resume: bool = True,
    ) -> List[TextChunk]:
        if self._book is None:
            raise ValueError("Book not loaded")

        try:
            self._log.info(
                "Prepare: book_id=%s voice=%s start_playback_index=%s start_char_offset=%s force_start_char=%s skip_essay_index=%s persist_resume=%s",
                getattr(self._book, "id", None),
                getattr(voice, "name", None),
                start_playback_index,
                start_char_offset,
                force_start_char,
                bool(skip_essay_index),
                bool(persist_resume),
            )
        except Exception:  # pragma: no cover
            pass
        self._voice = voice

        # New run: clear any pending stop-at-boundary request.
        try:
            self._stop_after_current_chunk.clear()
        except Exception:  # pragma: no cover
            pass

        self._persist_resume = bool(persist_resume)

        if start_playback_index is None and start_char_offset is None:
            # Auto-resume behavior: when a resume position exists, Play starts from
            # that chunk index without additional UI.
            resume_idx: int | None = None
            if self.bookmark_service is not None:
                try:
                    rp = self.bookmark_service.load_resume_position(
                        book_id=self._book.id
                    )
                except Exception:
                    rp = None
                if rp is not None:
                    resume_idx = int(rp.chunk_index)

            try:
                self._log.info(
                    "Prepare: auto-resume resume_idx=%s (bookmark_service=%s)",
                    resume_idx,
                    self.bookmark_service is not None,
                )
            except Exception:  # pragma: no cover
                pass
            self._start_playback_index = max(0, int(resume_idx or 0))
        elif start_playback_index is not None:
            self._start_playback_index = max(0, int(start_playback_index))
        else:
            # Defer mapping start_char_offset -> playback index until after we build
            # chunks (requires the same navigation filters and speak-text filtering).
            self._start_playback_index = 0

        # Reset play position tracking for the next run.
        self._current_play_index = -1

        assert self.navigation_chunk_service is not None
        chunks, start = self.navigation_chunk_service.build_chunks(
            book_text=self._book.normalized_text,
            force_start_char=force_start_char,
            skip_essay_index=bool(skip_essay_index),
        )
        self._start_char = int(start.start_char)
        self._log.debug("Narration start: %s at %s", start.reason, start.start_char)

        try:
            self._log.info(
                "Prepare: navigation start_char=%s reason=%s chunks=%s",
                int(start.start_char),
                start.reason,
                len(chunks),
            )
        except Exception:  # pragma: no cover
            pass
        self._cache_book_id = None

        self._set_state(
            NarrationState(
                status=NarrationStatus.CHUNKING,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message=f"Chunking text ({start.reason})...",
            )
        )

        self._chunks = list(chunks)

        # If we have an absolute start offset (e.g. Ideas Go To), we must ensure
        # playback begins from the first chunk containing/after that offset.
        #
        # NOTE: When `force_start_char` is used, chunk_id values reset to 0..N in
        # slice coordinates, so `_run()` will still start at chunk-local char 0.
        # To start at the *exact* target within the first chunk, we also need to
        # adjust the chunk text/offsets in-place.
        if start_char_offset is not None:
            try:
                absolute = int(start_char_offset)
            except Exception:  # pragma: no cover
                absolute = None
            if absolute is not None and self._chunks:
                for i, c in enumerate(self._chunks):
                    if int(c.start_char) <= absolute < int(c.end_char):
                        cut = max(0, absolute - int(c.start_char))
                        if cut:
                            self._chunks[i] = TextChunk(
                                chunk_id=int(c.chunk_id),
                                text=str(c.text)[cut:],
                                start_char=int(c.start_char) + int(cut),
                                end_char=int(c.end_char),
                            )
                        break
                    if int(c.start_char) >= absolute:
                        break

        if start_char_offset is not None:
            idx = self._resolve_playback_index_for_char_offset(
                char_offset=int(start_char_offset),
                chunks=self._chunks,
            )

            try:
                resolved = None if idx is None else int(idx)
                self._log.info(
                    "Prepare: start_char_offset=%s resolved_playback_index=%s",
                    int(start_char_offset),
                    resolved,
                )
                if resolved is not None:
                    c = self._chunks[resolved]
                    self._log.info(
                        "Prepare: resolved chunk_id=%s chunk_range=[%s,%s)",
                        int(c.chunk_id),
                        int(c.start_char),
                        int(c.end_char),
                    )
            except Exception:  # pragma: no cover
                pass
            if idx is not None:
                self._start_playback_index = max(0, int(idx))

        try:
            if start_char_offset is not None and self._chunks:
                c0 = self._chunks[0]
                self._log.info(
                    "Prepare: first_chunk after trim chunk_id=%s chunk_range=[%s,%s)",
                    int(c0.chunk_id),
                    int(c0.start_char),
                    int(c0.end_char),
                )
        except Exception:  # pragma: no cover
            pass
        self._set_state(
            NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=None,
                total_chunks=len(self._chunks),
                progress=0.0,
                message=f"Prepared {len(self._chunks)} chunks",
            )
        )
        return list(self._chunks)

    def _resolve_playback_index_for_char_offset(
        self, *, char_offset: int, chunks: List[TextChunk]
    ) -> int | None:
        """Map an absolute book char_offset to a playback candidate index.

        This must match candidate filtering used in [`_run()`](voice_reader/application/services/narration_service.py:484):
        candidates are chunks where sanitized speak_text is non-empty.
        """

        if not chunks:
            return None

        candidates: list[TextChunk] = []
        for c in chunks:
            mapped = self.sanitized_text_mapper.sanitize_with_mapping(original_text=c.text)
            if mapped.speak_text:
                candidates.append(c)

        if not candidates:
            return None

        try:
            self._log.info(
                "ResolveIndex: char_offset=%s playback_candidates=%s total_chunks=%s",
                int(char_offset),
                len(candidates),
                len(chunks),
            )
        except Exception:  # pragma: no cover
            pass

        for idx, c in enumerate(candidates):
            if int(c.start_char) <= int(char_offset) < int(c.end_char):
                return int(idx)
            if int(c.start_char) >= int(char_offset):
                return int(idx)
        return None

    def start(self) -> None:
        with self._lock:
            # New run: clear any previous stop-at-boundary request.
            try:
                self._stop_after_current_chunk.clear()
            except Exception:  # pragma: no cover
                pass
            if self._play_thread and self._play_thread.is_alive():
                try:
                    self._log.info(
                        "Start ignored: narration thread still alive (start_playback_index=%s)",
                        int(getattr(self, "_start_playback_index", 0)),
                    )
                except Exception:  # pragma: no cover
                    pass
                return
            if self._book is None or self._voice is None:
                raise ValueError("Book and voice must be set before start")
            if not self._chunks:
                self._chunks = self.chunking_service.chunk_text(
                    self._book.normalized_text
                )

            try:
                self._log.info(
                    "Start: book_id=%s voice=%s start_playback_index=%s chunks=%s",
                    getattr(self._book, "id", None),
                    getattr(self._voice, "name", None),
                    int(getattr(self, "_start_playback_index", 0)),
                    len(self._chunks),
                )
            except Exception:  # pragma: no cover
                pass
            self._stop_event.clear()
            self._play_thread = threading.Thread(
                target=self._run,
                name="narration-thread",
                daemon=True,
            )
            self._play_thread.start()

    def request_stop_after_current_chunk(self) -> None:
        """Request a graceful stop after the current chunk finishes."""

        try:
            self._log.info("StopAfterChunk: requested")
        except Exception:  # pragma: no cover
            pass
        try:
            self._stop_after_current_chunk.set()
        except Exception:  # pragma: no cover
            pass

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
        self._pause_event.set()
        self.audio_streamer.pause()

        # IMPORTANT:
        # `_state.current_chunk_id` is also used by SYNTHESIZING progress updates
        # (prefetch), which can run ahead of playback. When pausing (and later
        # switching voices), we must anchor to the *playback* position.
        paused_chunk_id = (
            self._current_play_index
            if self._current_play_index is not None and self._current_play_index >= 0
            else self._state.current_chunk_id
        )
        self._set_state(
            NarrationState(
                status=NarrationStatus.PAUSED,
                current_chunk_id=paused_chunk_id,
                playback_chunk_id=paused_chunk_id,
                prefetch_chunk_id=self._state.prefetch_chunk_id,
                total_chunks=self._state.total_chunks,
                progress=self._state.progress,
                message="Paused",
                audible_start=self._state.audible_start,
                audible_end=self._state.audible_end,
                highlight_start=self._state.highlight_start,
                highlight_end=self._state.highlight_end,
            )
        )

        # Persist resume after state has been updated.
        self._maybe_save_resume_position()

    def resume(self) -> None:
        # Resume means: restart the current chunk from the beginning.
        # The AudioStreamer implementation handles the chunk replay semantics.
        self._pause_event.clear()
        self.audio_streamer.resume()
        self._set_state(
            NarrationState(
                status=NarrationStatus.PLAYING,
                current_chunk_id=self._state.current_chunk_id,
                playback_chunk_id=self._state.current_chunk_id,
                prefetch_chunk_id=self._state.prefetch_chunk_id,
                total_chunks=self._state.total_chunks,
                progress=self._state.progress,
                message="Playing",
                audible_start=self._state.audible_start,
                audible_end=self._state.audible_end,
                highlight_start=self._state.highlight_start,
                highlight_end=self._state.highlight_end,
            )
        )

    def stop(self, *, persist_resume: bool = True) -> None:
        # Capture resume before we clear state/highlighting.
        if bool(persist_resume):
            self._maybe_save_resume_position()

        try:
            self._log.info(
                "Stop: signalling stop (thread_alive=%s)",
                bool(self._play_thread and self._play_thread.is_alive()),
            )
        except Exception:  # pragma: no cover
            pass
        self._stop_event.set()
        try:
            self._stop_after_current_chunk.clear()
        except Exception:  # pragma: no cover
            pass
        self._pause_event.clear()
        self.audio_streamer.stop()

        # Ensure the narration thread has terminated so a subsequent start() is
        # not ignored due to an "already alive" thread.
        self.wait(timeout_seconds=2.0)

        try:
            self._log.info(
                "Stop: completed (thread_alive=%s)",
                bool(self._play_thread and self._play_thread.is_alive()),
            )
        except Exception:  # pragma: no cover
            pass

        self._set_state(
            NarrationState(
                status=NarrationStatus.STOPPED,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=None,
                total_chunks=self._state.total_chunks,
                progress=0.0,
                message="Stopped",
                audible_start=None,
                audible_end=None,
                highlight_start=None,
                highlight_end=None,
            )
        )

        # Reset persistence policy after a run finishes.
        self._persist_resume = True

    def on_app_exit(self) -> None:
        """Persist resume position on application exit.

        This should be called from the Qt `aboutToQuit` hook.
        """

        self._maybe_save_resume_position()

    def book_id(self) -> str:
        if self._book is None:
            raise ValueError("Book not loaded")
        # Stable hash to key cache.
        # IMPORTANT: include the detected start offset and a version tag so we
        # don't reuse old chunk0 audio after changing front-matter skipping or
        # spoken-text sanitization.
        # IMPORTANT: include the TTS engine name so we don't reuse audio across
        # different engines (e.g., pyttsx3 fallback vs Coqui XTTS voice cloning).
        if self._cache_book_id is not None:
            return self._cache_book_id

        if self._start_char is None:
            start = self.reading_start_detector.detect_start(self._book.normalized_text)
            self._start_char = start.start_char

        # Bump version when changing audio-affecting logic.
        # - v4: include engine tag
        # - v5: spoken text sanitizer newline->space; chunking omission bugfix
        # - v6: XTTS reference selection/capping changes (quality-affecting)
        # - v7: acronym expansion + punctuation normalization
        # - v8: dot-like char normalization improvements
        # - v9: voice reference selection filtering (avoid derived PCM16)
        # - v10: reference window selection for long/noisy reference clips
        # - v11: remove first-chunk truncation debug hack (was skipping content)
        # - v12: synthesis prefetch changes (gap reduction)
        # - v13: deterministic seeding (reduce voice drift)
        # - v14: disable XTTS internal sentence splitting (reduce repeats)
        version_tag = "v14"
        engine_tag = self.tts_engine.engine_name.strip().lower()
        payload = (
            f"{self._book.normalized_text}|"
            f"start={self._start_char}|"
            f"engine={engine_tag}|"
            f"{version_tag}"
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._cache_book_id = digest[:16]
        return self._cache_book_id

    def _run(self) -> None:
        assert self._book is not None
        assert self._voice is not None

        # Capture locals to avoid Optional narrowing issues inside nested closures.
        voice = self._voice
        tts_engine = self.tts_engine
        book_id = self.book_id()
        playback_chunks: List[TextChunk] = []
        # Per playback index, store (speak_text, speak_to_original mapping).
        playback_text_maps: list[tuple[str, list[int]]] = []
        try:
            # Pre-compute playback candidates to:
            # - keep UI totals stable
            # - stream audio as soon as each chunk is ready (no waiting for full
            #   book synthesis)
            # candidates carries:
            # - chunk: original chunk with absolute book offsets
            # - speak_text: sanitized text for TTS
            # - speak_to_orig: per-character map speak_text index -> chunk-local index
            # - path: cached wav path
            candidates: list[tuple[TextChunk, str, list[int], Path]] = []
            for chunk in self._chunks:
                mapped = self.sanitized_text_mapper.sanitize_with_mapping(
                    original_text=chunk.text
                )
                speak_text = mapped.speak_text
                if not speak_text:
                    continue
                path = self.cache_repo.audio_path(
                    book_id=book_id,
                    voice_name=voice.name,
                    chunk_id=chunk.chunk_id,
                )
                candidates.append((chunk, speak_text, mapped.speak_to_original, path))

            # Support restarting from a given playback index (e.g. voice change
            # while paused). This is *playback index* into the candidate list.
            start_idx = max(0, min(int(self._start_playback_index), len(candidates)))
            if start_idx:
                candidates = candidates[start_idx:]

            playback_total = len(candidates)
            self._log.debug(
                "Narration _run: engine=%s voice=%s candidates=%s device=%s language=%s",
                tts_engine.engine_name,
                voice.name,
                playback_total,
                self.device,
                self.language,
            )

            # Producer/consumer boundary:
            # - a synth thread ensures cache and pushes ready-to-play paths
            # - the audio streamer consumes paths and plays them
            #
            # This allows synthesis to run ahead of playback (reduces gaps).
            path_q: "queue.Queue[Path | None]" = queue.Queue(maxsize=8)
            synth_done = threading.Event()
            synth_errors: list[BaseException] = []

            warmup_enabled = os.getenv("NARRATEX_WARMUP", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }

            def _synth_worker() -> None:
                try:
                    if warmup_enabled:
                        try:
                            # Warm the model/codepaths without altering narrated text.
                            tmp = (
                                self.cache_repo.audio_path(
                                    book_id=book_id,
                                    voice_name=voice.name,
                                    chunk_id=-999999,
                                )
                            ).with_name("__warmup.wav")
                            self.cache_repo.ensure_parent_dir(tmp)
                            self._log.debug(
                                "Warmup synthesis start (path=%s)", tmp.as_posix()
                            )
                            tts_engine.synthesize_to_file(
                                text="Warmup.",
                                voice_profile=voice,
                                output_path=tmp,
                                device=self.device,
                                language=self.language,
                            )
                            try:
                                tmp.unlink(missing_ok=True)
                            except Exception:
                                pass
                            self._log.debug("Warmup synthesis done")
                        except Exception:
                            self._log.exception("Warmup synthesis failed")

                    for idx, (chunk, speak_text, speak_to_orig, path) in enumerate(
                        candidates
                    ):
                        if self._stop_event.is_set():
                            return

                        # Limit how far synthesis can run ahead of playback.
                        # This prevents synthesizing an entire book quickly on
                        # fast engines, and also supports pause semantics.
                        try:
                            max_ahead = int(os.getenv("NARRATEX_MAX_AHEAD_CHUNKS", "6"))
                        except Exception:
                            max_ahead = 6

                        # When paused, allow 0-ahead: only synthesize up to the
                        # currently playing chunk.
                        allowed_ahead = (
                            0 if self._pause_event.is_set() else max(0, max_ahead)
                        )

                        # Gate using a dynamically-read playback index so we
                        # don't deadlock when playback advances while we're
                        # waiting.
                        while not self._stop_event.is_set():
                            base_play = self._current_play_index
                            if base_play < 0:
                                # If playback hasn't started yet, allow a small
                                # initial window.
                                base_play = allowed_ahead
                            if idx <= (int(base_play) + allowed_ahead):
                                break
                            time.sleep(0.05)

                        if self._stop_event.is_set():
                            return

                        self._set_state(
                            NarrationState(
                                status=NarrationStatus.SYNTHESIZING,
                                # Do not advance playback chunk id while prefetching.
                                current_chunk_id=self._state.current_chunk_id,
                                prefetch_chunk_id=idx,
                                playback_chunk_id=self._state.current_chunk_id,
                                total_chunks=playback_total,
                                progress=idx / max(playback_total, 1),
                                message=f"Preparing chunk {idx + 1}/{playback_total}",
                            )
                        )

                        if not self.cache_repo.exists(
                            book_id=book_id,
                            voice_name=voice.name,
                            chunk_id=chunk.chunk_id,
                        ):
                            self.cache_repo.ensure_parent_dir(path)
                            t0 = time.perf_counter()
                            self._log.debug(
                                "TTS start idx=%s chunk_id=%s text_len=%s out=%s",
                                idx,
                                chunk.chunk_id,
                                len(speak_text),
                                path.as_posix(),
                            )
                            tts_engine.synthesize_to_file(
                                text=speak_text,
                                voice_profile=voice,
                                output_path=path,
                                device=self.device,
                                language=self.language,
                            )
                            elapsed = time.perf_counter() - t0
                            size = None
                            try:
                                size = path.stat().st_size
                            except Exception:
                                pass
                            self._log.debug(
                                "TTS done idx=%s elapsed=%.2fs size_bytes=%s out=%s",
                                idx,
                                elapsed,
                                size,
                                path.as_posix(),
                            )
                        else:
                            self._log.debug(
                                "Cache hit idx=%s chunk_id=%s out=%s",
                                idx,
                                chunk.chunk_id,
                                path.as_posix(),
                            )

                        # Append BEFORE publishing path so on_start can map.
                        playback_chunks.append(chunk)
                        playback_text_maps.append((speak_text, speak_to_orig))
                        self._log.debug(
                            "Publishing audio path idx=%s out=%s",
                            idx,
                            path.as_posix(),
                        )
                        path_q.put(path)
                except BaseException as exc:  # pragma: no cover
                    synth_errors.append(exc)
                    self._log.exception("Synthesis worker failed")
                finally:
                    synth_done.set()
                    # Signal end-of-stream to path iterator.
                    try:
                        path_q.put_nowait(None)
                    except Exception:
                        try:
                            path_q.put(None)
                        except Exception:
                            pass

            # Optional Kokoro-only parallel synthesis: run ahead using multiple
            # workers, but still publish paths in-order. This accelerates
            # CPU-native Kokoro generation on multi-core machines.
            try:
                kokoro_workers = int(os.getenv("NARRATEX_KOKORO_WORKERS", "0"))
            except Exception:
                kokoro_workers = 0

            # Detect "Kokoro-native" mode, even when wrapped in Hybrid.
            is_kokoro_native = False
            try:
                if voice.reference_audio_paths:
                    is_kokoro_native = False
                elif tts_engine.engine_name.strip().lower() == "kokoro":
                    is_kokoro_native = True
                else:
                    native = getattr(tts_engine, "native_engine", None)
                    if (
                        native is not None
                        and getattr(native, "engine_name", "").strip().lower()
                        == "kokoro"
                    ):
                        is_kokoro_native = True
            except Exception:
                is_kokoro_native = False

            if is_kokoro_native and kokoro_workers and kokoro_workers > 1:
                self._log.debug(
                    "Parallel Kokoro synthesis enabled: workers=%s max_ahead=%s",
                    int(kokoro_workers),
                    os.getenv("NARRATEX_MAX_AHEAD_CHUNKS", "6"),
                )
                # Replace queue and events for parallel path publishing.
                path_q = queue.Queue(maxsize=8)
                synth_done = threading.Event()
                synth_errors = []

                # Work queue carries (idx, chunk, text, path).
                work_q: "queue.Queue[tuple[int, TextChunk, str, Path] | None]" = (
                    queue.Queue()
                )
                for i, (c, t, _m, p) in enumerate(candidates):
                    work_q.put((i, c, t, p))
                for _ in range(int(kokoro_workers)):
                    work_q.put(None)

                results: dict[int, Path] = {}
                results_lock = threading.Lock()

                def _worker() -> None:
                    try:
                        while not self._stop_event.is_set():
                            item = work_q.get()
                            if item is None:
                                return
                            i, chunk, speak_text, path = item

                            # Respect max-ahead and pause semantics.
                            try:
                                max_ahead = int(
                                    os.getenv("NARRATEX_MAX_AHEAD_CHUNKS", "6")
                                )
                            except Exception:
                                max_ahead = 6
                            allowed_ahead = (
                                0 if self._pause_event.is_set() else max(0, max_ahead)
                            )
                            while not self._stop_event.is_set():
                                base_play = self._current_play_index
                                if base_play < 0:
                                    base_play = allowed_ahead
                                if i <= (int(base_play) + allowed_ahead):
                                    break
                                time.sleep(0.05)

                            if self._pause_event.is_set():
                                while (
                                    self._pause_event.is_set()
                                    and not self._stop_event.is_set()
                                    and i > max(self._current_play_index, 0)
                                ):
                                    time.sleep(0.05)

                            if self._stop_event.is_set():
                                return

                            if not self.cache_repo.exists(
                                book_id=book_id,
                                voice_name=voice.name,
                                chunk_id=chunk.chunk_id,
                            ):
                                self.cache_repo.ensure_parent_dir(path)
                                tts_engine.synthesize_to_file(
                                    text=speak_text,
                                    voice_profile=voice,
                                    output_path=path,
                                    device=self.device,
                                    language=self.language,
                                )

                            with results_lock:
                                results[i] = path
                    except BaseException as exc:  # pragma: no cover
                        synth_errors.append(exc)

                for i in range(int(kokoro_workers)):
                    threading.Thread(
                        target=_worker,
                        name=f"tts-kokoro-{i}",
                        daemon=True,
                    ).start()

                def _publisher() -> None:
                    try:
                        next_idx = 0
                        while not self._stop_event.is_set() and next_idx < len(
                            candidates
                        ):
                            with results_lock:
                                path = results.get(next_idx)
                            if path is None:
                                time.sleep(0.01)
                                continue
                            playback_chunks.append(candidates[next_idx][0])
                            playback_text_maps.append(
                                (candidates[next_idx][1], candidates[next_idx][2])
                            )
                            path_q.put(path)
                            next_idx += 1
                    finally:
                        synth_done.set()
                        try:
                            path_q.put_nowait(None)
                        except Exception:
                            try:
                                path_q.put(None)
                            except Exception:
                                pass

                threading.Thread(
                    target=_publisher,
                    name="tts-publisher",
                    daemon=True,
                ).start()
            else:
                synth_thread = threading.Thread(
                    target=_synth_worker,
                    name="tts-synth",
                    daemon=True,
                )
                synth_thread.start()

            # Optional prefetch: wait for a couple paths to be ready so playback
            # doesn't pause between early chunks.
            try:
                prefetch = int(os.getenv("NARRATEX_PREFETCH_CHUNKS", "2"))
            except Exception:
                prefetch = 2
            if prefetch > 0:
                t0_prefetch = time.perf_counter()
                while (
                    not synth_done.is_set()
                    and path_q.qsize() < prefetch
                    and not self._stop_event.is_set()
                    and (time.perf_counter() - t0_prefetch) < 30.0
                ):
                    time.sleep(0.05)

            def audio_paths_iter():
                self._log.debug("audio_paths_iter: start")
                while not self._stop_event.is_set():
                    item = path_q.get()
                    if item is None:
                        self._log.debug("audio_paths_iter: exhausted")
                        return
                    yield item

            def on_start(play_index: int) -> None:
                # Track the playback position for pause-aware synthesis gating.
                self._current_play_index = int(play_index)
                if play_index < 0 or play_index >= playback_total:
                    return
                c = playback_chunks[play_index]
                # Reset per-chunk progress clock.
                try:
                    # Used by on_progress fallback throttling.
                    on_progress._last_emit_ms = -1  # type: ignore[attr-defined]
                except Exception:
                    pass
                self._set_state(
                    NarrationState(
                        status=NarrationStatus.PLAYING,
                        current_chunk_id=play_index,
                        playback_chunk_id=play_index,
                        prefetch_chunk_id=self._state.prefetch_chunk_id,
                        total_chunks=playback_total,
                        progress=play_index / max(playback_total, 1),
                        message=f"Playing chunk {play_index + 1}/{playback_total}",
                        # Audible highlight will be driven by playback progress.
                        # Start with a safe chunk-level fallback.
                        audible_start=c.start_char,
                        audible_end=c.end_char,
                        highlight_start=c.start_char,
                        highlight_end=c.end_char,
                    )
                )

            def on_end(play_index: int) -> None:
                # If a queued navigation requested a graceful stop, stop right
                # after the current chunk completes.
                try:
                    if not self._stop_after_current_chunk.is_set():
                        return
                except Exception:  # pragma: no cover
                    return

                try:
                    self._log.info(
                        "StopAfterChunk: stopping after chunk_end play_index=%s",
                        int(play_index),
                    )
                except Exception:  # pragma: no cover
                    pass

                # Set both stop signals so synthesis and playback wind down.
                try:
                    self._stop_after_current_chunk.clear()
                except Exception:  # pragma: no cover
                    pass
                self._stop_event.set()
                try:
                    self.audio_streamer.stop()
                except Exception:  # pragma: no cover
                    pass

            def on_progress(play_index: int, chunk_local_ms: int) -> None:
                # Resolve audible highlight span from per-chunk alignment.
                if play_index < 0 or play_index >= playback_total:
                    return
                c = playback_chunks[play_index]

                # Throttle to ~30-50ms even if backend calls faster.
                try:
                    last = int(getattr(on_progress, "_last_emit_ms", -1))  # type: ignore[attr-defined]
                except Exception:
                    last = -1
                ms = int(max(0, chunk_local_ms))
                if last >= 0 and (ms - last) < 25:
                    return
                try:
                    on_progress._last_emit_ms = ms  # type: ignore[attr-defined]
                except Exception:
                    pass

                # If paused/stopped, freeze highlight updates.
                if self._pause_event.is_set() or self._stop_event.is_set():
                    return

                # Load/generate alignment.
                align = None
                try:
                    chunk_id = int(c.chunk_id)
                    ap = self.cache_repo.alignment_path(
                        book_id=book_id, voice_name=voice.name, chunk_id=chunk_id
                    )
                    align = self.alignment_io.load(ap) if ap.exists() else None
                except Exception:
                    align = None

                if align is None:
                    # Estimate from sanitized speak_text + mapping and audio duration.
                    try:
                        speak_text, speak_to_orig = playback_text_maps[play_index]
                    except Exception:
                        speak_text, speak_to_orig = "", []

                    # Derive duration. Prefer WAV length; fall back to last known ms.
                    duration_ms = 0
                    try:
                        import soundfile as sf

                        wav_path = self.cache_repo.audio_path(
                            book_id=book_id,
                            voice_name=voice.name,
                            chunk_id=int(c.chunk_id),
                        )
                        with sf.SoundFile(str(wav_path)) as f:
                            duration_ms = int(
                                round((len(f) / float(f.samplerate)) * 1000.0)
                            )
                    except Exception:
                        duration_ms = max(ms, 1)

                    # Generate alignment in chunk-local coordinates, then shift to book offsets.
                    est = self.estimated_aligner.estimate(
                        chunk_id=int(c.chunk_id),
                        speak_text=speak_text,
                        speak_to_original=speak_to_orig,
                        duration_ms=duration_ms,
                    )
                    from voice_reader.domain.alignment.model import TimedTextSpan

                    spans: list[TimedTextSpan] = []
                    for s in est.spans:
                        spans.append(
                            TimedTextSpan(
                                start_char=int(c.start_char) + int(s.start_char),
                                end_char=int(c.start_char) + int(s.end_char),
                                audio_start_ms=int(s.audio_start_ms),
                                audio_end_ms=int(s.audio_end_ms),
                                confidence=float(s.confidence),
                            )
                        )
                    align = ChunkAlignment(
                        chunk_id=int(c.chunk_id),
                        duration_ms=est.duration_ms,
                        spans=spans,
                    )

                    # Best-effort persist alignment alongside wav cache.
                    try:
                        ap = self.cache_repo.alignment_path(
                            book_id=book_id,
                            voice_name=voice.name,
                            chunk_id=int(c.chunk_id),
                        )
                        self.alignment_io.save(path=ap, alignment=align)
                    except Exception:
                        pass

                a_start, a_end = self.playback_synchronizer.resolve_span(
                    alignment=align, chunk_local_ms=ms
                )

                # Final fallback: whole chunk.
                if a_start is None or a_end is None:
                    a_start, a_end = int(c.start_char), int(c.end_char)

                # Avoid flooding listeners if nothing changes.
                st = self._state
                if (
                    st.playback_chunk_id == play_index
                    and st.audible_start == a_start
                    and st.audible_end == a_end
                ):
                    return
                self._set_state(
                    NarrationState(
                        status=st.status,
                        current_chunk_id=play_index,
                        playback_chunk_id=play_index,
                        prefetch_chunk_id=st.prefetch_chunk_id,
                        total_chunks=st.total_chunks,
                        progress=st.progress,
                        message=st.message,
                        audible_start=a_start,
                        audible_end=a_end,
                        highlight_start=st.highlight_start,
                        highlight_end=st.highlight_end,
                    )
                )

            self.audio_streamer.start(
                chunk_audio_paths=audio_paths_iter(),
                on_chunk_start=on_start,
                on_chunk_end=on_end,
                on_playback_progress=on_progress,
            )

            if synth_errors:
                raise synth_errors[0]

            if self._stop_event.is_set():
                # A stop request occurred (user stop, or stop-after-chunk).
                self._set_state(
                    NarrationState(
                        status=NarrationStatus.STOPPED,
                        current_chunk_id=None,
                        playback_chunk_id=None,
                        prefetch_chunk_id=None,
                        total_chunks=playback_total,
                        progress=0.0,
                        message="Stopped",
                        audible_start=None,
                        audible_end=None,
                        highlight_start=None,
                        highlight_end=None,
                    )
                )
                return

            self._set_state(
                NarrationState(
                    status=NarrationStatus.IDLE,
                    current_chunk_id=None,
                    playback_chunk_id=None,
                    prefetch_chunk_id=self._state.prefetch_chunk_id,
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
                    playback_chunk_id=self._state.playback_chunk_id,
                    prefetch_chunk_id=self._state.prefetch_chunk_id,
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
