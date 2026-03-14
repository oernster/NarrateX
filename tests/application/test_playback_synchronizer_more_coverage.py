from __future__ import annotations

from voice_reader.application.services.playback_synchronizer import PlaybackSynchronizer
from voice_reader.domain.alignment.model import ChunkAlignment, TimedTextSpan


def test_resolve_span_returns_none_when_no_spans() -> None:
    s = PlaybackSynchronizer()
    alignment = ChunkAlignment(chunk_id=1, duration_ms=1000, spans=[])
    assert s.resolve_span(alignment=alignment, chunk_local_ms=0) == (None, None)


def test_resolve_span_before_first_snaps_to_first() -> None:
    s = PlaybackSynchronizer()
    alignment = ChunkAlignment(
        chunk_id=1,
        duration_ms=1000,
        spans=[
            TimedTextSpan(
                start_char=10,
                end_char=20,
                audio_start_ms=100,
                audio_end_ms=200,
                confidence=1.0,
            ),
            TimedTextSpan(
                start_char=21,
                end_char=30,
                audio_start_ms=200,
                audio_end_ms=300,
                confidence=1.0,
            ),
        ],
    )
    assert s.resolve_span(alignment=alignment, chunk_local_ms=0) == (10, 20)


def test_resolve_span_beyond_last_snaps_to_last() -> None:
    s = PlaybackSynchronizer()
    alignment = ChunkAlignment(
        chunk_id=1,
        duration_ms=1000,
        spans=[
            TimedTextSpan(
                start_char=1,
                end_char=2,
                audio_start_ms=0,
                audio_end_ms=10,
                confidence=1.0,
            )
        ],
    )
    assert s.resolve_span(alignment=alignment, chunk_local_ms=9999) == (1, 2)
