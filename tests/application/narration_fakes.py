"""The stand-in narration service, and the chunk and state helpers.

The narration helpers take the whole service and read its internals, so testing
them needs an object with the right attributes rather than the real service and
its audio device. The collaborators it holds live in
`narration_collaborators.py` and are re-exported here, so a test imports
everything it needs from one place.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from voice_reader.application.dto.narration_state import (
    NarrationState,
    NarrationStatus,
)
from voice_reader.application.services.narration.position import current_position
from voice_reader.domain.entities.text_chunk import TextChunk

from tests.application.narration_collaborators import (  # noqa: F401
    Boom,
    FakeAlignmentIO,
    FakeAudioStreamer,
    FakeBookRepo,
    FakeBookmarkService,
    FakeCacheRepo,
    FakeChunkingService,
    FakeEngine,
    FakeEstimate,
    FakeEstimatedAligner,
    FakeLog,
    FakeMapper,
    FakeMapping,
    FakeNavigationChunkService,
    FakePreferencesRepo,
    FakeResumePosition,
    FakeSpan,
    FakeStart,
    FakeSynchronizer,
)


@dataclass
class FakeBook:
    normalized_text: str
    document_model: object = None
    id: str = "book-1"
    title: str = "A Book"


def make_chunks(*texts: str) -> list[TextChunk]:
    """Chunks laid end to end, so offsets are contiguous."""

    chunks: list[TextChunk] = []
    start = 0
    for i, text in enumerate(texts):
        chunks.append(
            TextChunk(
                chunk_id=i, text=text, start_char=start, end_char=start + len(text)
            )
        )
        start += len(text)
    return chunks


def make_state(**overrides) -> NarrationState:
    defaults = {
        "status": NarrationStatus.PLAYING,
        "current_chunk_id": None,
        "total_chunks": None,
        "progress": 0.0,
    }
    defaults.update(overrides)
    return NarrationState(**defaults)


@dataclass
class FakeNarrationService:
    """Only the attributes the narration helpers actually read."""

    state: NarrationState = field(default_factory=make_state)
    _chunks: list[TextChunk] = field(default_factory=list)
    _start_playback_index: int = 0
    _cache_book_id: str | None = None
    _book: FakeBook | None = None
    _voice: object = None
    _start_char: int | None = None
    _played_any_chunk: bool = False
    _persist_resume: bool = True
    _current_play_index: int | None = None
    _play_thread: threading.Thread | None = None
    tts_engine: FakeEngine = field(default_factory=FakeEngine)
    sanitized_text_mapper: FakeMapper = field(default_factory=FakeMapper)
    cache_repo: FakeCacheRepo = field(default_factory=FakeCacheRepo)
    alignment_io: FakeAlignmentIO = field(default_factory=FakeAlignmentIO)
    estimated_aligner: FakeEstimatedAligner = field(
        default_factory=FakeEstimatedAligner
    )
    playback_synchronizer: FakeSynchronizer = field(default_factory=FakeSynchronizer)
    audio_streamer: FakeAudioStreamer = field(default_factory=FakeAudioStreamer)
    bookmark_service: FakeBookmarkService | None = field(
        default_factory=FakeBookmarkService
    )
    chunking_service: FakeChunkingService = field(default_factory=FakeChunkingService)
    preferences_repo: FakePreferencesRepo | None = field(
        default_factory=FakePreferencesRepo
    )
    book_repo: FakeBookRepo = field(default_factory=FakeBookRepo)
    navigation_chunk_service: FakeNavigationChunkService | None = field(
        default_factory=FakeNavigationChunkService
    )
    device: str = "cpu"
    language: str = "en"
    fail_stop: bool = False
    _log: FakeLog = field(default_factory=FakeLog)

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._stop_after_current_chunk = threading.Event()
        self.states: list[NarrationState] = []
        self.ran = threading.Event()
        self.stops: list[bool] = []

    def stop(self, *, persist_resume: bool = True) -> None:
        if self.fail_stop:
            raise Boom("stop")
        self.stops.append(persist_resume)

    def book_id(self) -> str:
        return "cache-id"

    def _maybe_save_resume_position(self) -> None:
        self.stops.append(True)

    def _set_state(self, state: NarrationState) -> None:
        self.state = state
        self.states.append(state)

    def _run(self) -> None:
        self.ran.set()

    def current_position(self) -> tuple[int | None, int | None]:
        return current_position(self)
