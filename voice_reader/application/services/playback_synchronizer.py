"""Application service: resolve audible highlight span from playback progress."""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.alignment.model import ChunkAlignment


@dataclass(frozen=True, slots=True)
class PlaybackSynchronizer:
    """Map (chunk_local_ms) -> (audible_start, audible_end) for a given alignment."""

    def resolve_span(
        self, *, alignment: ChunkAlignment, chunk_local_ms: int
    ) -> tuple[int | None, int | None]:
        ms = max(0, int(chunk_local_ms))
        spans = alignment.spans
        if not spans:
            return None, None

        # Find first span whose window contains ms.
        for s in spans:
            if s.audio_start_ms <= ms < s.audio_end_ms:
                return int(s.start_char), int(s.end_char)

        # If beyond end, snap to last span.
        last = spans[-1]
        if ms >= last.audio_end_ms:
            return int(last.start_char), int(last.end_char)

        # If before start, snap to first.
        first = spans[0]
        return int(first.start_char), int(first.end_char)

