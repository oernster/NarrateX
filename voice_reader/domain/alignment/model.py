"""Domain models for chunk text/audio alignment.

Alignment is expressed in reader (original book) character offsets.

Phase 1 uses estimated timings derived from text + WAV duration.
Phase 2 can populate these models from backend-provided timing metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class TimedTextSpan:
    start_char: int
    end_char: int
    audio_start_ms: int
    audio_end_ms: int
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "TimedTextSpan":
        return TimedTextSpan(
            start_char=int(d["start_char"]),
            end_char=int(d["end_char"]),
            audio_start_ms=int(d["audio_start_ms"]),
            audio_end_ms=int(d["audio_end_ms"]),
            confidence=float(d.get("confidence", 0.5)),
        )


@dataclass(frozen=True, slots=True)
class ChunkAlignment:
    chunk_id: int
    duration_ms: int
    spans: list[TimedTextSpan]

    def to_dict(self) -> dict:
        return {
            "chunk_id": int(self.chunk_id),
            "duration_ms": int(self.duration_ms),
            "spans": [s.to_dict() for s in self.spans],
        }

    @staticmethod
    def from_dict(d: dict) -> "ChunkAlignment":
        spans = [TimedTextSpan.from_dict(x) for x in (d.get("spans") or [])]
        return ChunkAlignment(
            chunk_id=int(d["chunk_id"]),
            duration_ms=int(d.get("duration_ms", 0)),
            spans=spans,
        )

