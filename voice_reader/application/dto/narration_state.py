"""DTOs describing narration progress/state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NarrationStatus(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    CHUNKING = "chunking"
    SYNTHESIZING = "synthesizing"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class NarrationState:
    status: NarrationStatus
    # Backwards-compatible field historically used as both prefetch and playback.
    # Going forward this should represent the *playback* chunk index.
    current_chunk_id: int | None
    total_chunks: int | None
    progress: float
    message: str = ""

    # ---- Highlighting (reader offsets) ----
    # New model: UI should drive visible highlight from audible_start/audible_end.
    audible_start: int | None = None
    audible_end: int | None = None

    # Legacy highlighting fields kept for compatibility with older callers/tests.
    highlight_start: int | None = None
    highlight_end: int | None = None

    # ---- Chunk lifecycle split (prefetch vs playback) ----
    # Prefetch chunk index into the playback candidate list, used for synth/cache
    # progress UI only. Must not drive reader highlighting.
    prefetch_chunk_id: int | None = None

    # Playback chunk index into the playback candidate list.
    playback_chunk_id: int | None = None
