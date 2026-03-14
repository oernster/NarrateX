from __future__ import annotations

from voice_reader.domain.alignment.estimated_aligner import EstimatedAligner


def test_estimated_aligner_produces_spans_and_monotonic_timings() -> None:
    speak = "Hello world. This is a test."
    # Identity mapping for simplicity.
    mapping = list(range(len(speak)))
    a = EstimatedAligner()
    out = a.estimate(
        chunk_id=1,
        speak_text=speak,
        speak_to_original=mapping,
        duration_ms=1000,
    )
    assert out.chunk_id == 1
    assert out.duration_ms == 1000
    assert out.spans, "expected some spans"
    # Timings should be monotonic and within duration.
    last_end = 0
    for s in out.spans:
        assert 0 <= s.audio_start_ms <= s.audio_end_ms <= 1000
        assert s.audio_start_ms >= last_end or s.audio_start_ms == 0
        last_end = s.audio_end_ms


def test_estimated_aligner_handles_empty_input() -> None:
    a = EstimatedAligner()
    out = a.estimate(
        chunk_id=0,
        speak_text="",
        speak_to_original=[],
        duration_ms=0,
    )
    assert out.spans == []
