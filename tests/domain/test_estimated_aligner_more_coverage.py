from __future__ import annotations

from voice_reader.domain.alignment.estimated_aligner import EstimatedAligner


def test_estimated_aligner_returns_empty_when_no_tokens() -> None:
    a = EstimatedAligner()

    # Only whitespace -> no tokens.
    out = a.estimate(
        chunk_id=1,
        speak_text="   ",
        speak_to_original=[0],
        duration_ms=1000,
    )
    assert out.chunk_id == 1
    assert out.duration_ms == 1000
    assert out.spans == []


def test_estimated_aligner_skips_when_mapping_missing_or_out_of_range() -> None:
    a = EstimatedAligner()

    # Missing mapping -> spans empty.
    out = a.estimate(
        chunk_id=2,
        speak_text="Hello world",
        speak_to_original=[],
        duration_ms=1000,
    )
    assert out.spans == []

    # start_i beyond mapping length -> spans empty.
    out2 = a.estimate(
        chunk_id=3,
        speak_text="Hello",
        # Mapping too short: only index 0 is valid. The implementation will emit
        # a span for the first token char but skip the rest.
        speak_to_original=[0],
        duration_ms=1000,
    )
    assert len(out2.spans) == 1


def test_estimated_aligner_swaps_reversed_mapping_and_fixes_last_end_ms() -> None:
    # Force a case where o_end < o_start by using a reversed mapping.
    # speak_text indices: 0..3
    # mapping: [3, 2, 1, 0] so token start maps to later than token end.
    a = EstimatedAligner()
    out = a.estimate(
        chunk_id=9,
        speak_text="ABCD",
        speak_to_original=[3, 2, 1, 0],
        duration_ms=1234,
    )
    assert out.spans
    assert out.spans[0].start_char <= out.spans[0].end_char
    # Last span should be pinned to duration.
    assert out.spans[-1].audio_end_ms == 1234
