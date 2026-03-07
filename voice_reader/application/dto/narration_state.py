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
    current_chunk_id: int | None
    total_chunks: int | None
    progress: float
    message: str = ""
    highlight_start: int | None = None
    highlight_end: int | None = None
