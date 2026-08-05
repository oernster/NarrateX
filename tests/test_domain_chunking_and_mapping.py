"""Edge paths in the pure-domain chunking, mapping and alignment services.

These three modules were outside the coverage gate. They are pure domain, so
there was no fragility excuse: every branch below is reachable with plain
inputs and no fakes at all.
"""

from voice_reader.domain.alignment.estimated_aligner import EstimatedAligner
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper

# ---------------------------------------------------------------------------
# ChunkingService
# ---------------------------------------------------------------------------


def test_repeated_terminators_do_not_produce_empty_chunks():
    # An ellipsis splits awkwardly. Nothing zero-length may reach the narrator,
    # since an empty chunk is silence in the middle of the audio.
    service = ChunkingService(min_chars=5, max_chars=40)

    chunks = service.chunk_text("First one... Second one.")

    assert chunks
    assert all(chunk.text.strip() for chunk in chunks)


def test_a_short_pending_chunk_is_emitted_before_a_long_sentence_is_wrapped():
    # The regression this guards: when the pending text was shorter than
    # min_chars and the next sentence was longer, the pending text used to be
    # dropped outright, silently omitting a sentence from the audio.
    service = ChunkingService(min_chars=20, max_chars=40)
    short = "Tiny bit."
    long_sentence = "This sentence is comfortably longer than the minimum size."

    chunks = service.chunk_text(f"{short} {long_sentence}")
    joined = " ".join(chunk.text for chunk in chunks)

    assert "Tiny bit." in joined
    assert "comfortably longer" in joined


def test_every_chunk_reports_offsets_that_match_its_text():
    service = ChunkingService(min_chars=10, max_chars=30)
    text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota kappa lambda."

    chunks = service.chunk_text(text)

    assert chunks
    for chunk in chunks:
        assert chunk.end_char > chunk.start_char


# ---------------------------------------------------------------------------
# SanitizedTextMapper
# ---------------------------------------------------------------------------


def test_an_expanded_acronym_still_maps_every_spoken_character():
    # The sanitizer spells all-caps words out letter by letter, so the spoken
    # text grows and gains spaces the original never had. That drives both
    # awkward paths at once: a spoken space has to skip forward over original
    # letters to reach real whitespace, and the inserted letters have no
    # counterpart left to find, so the mapper clamps instead of failing.
    original = "ONE two"
    mapper = SanitizedTextMapper()

    result = mapper.sanitize_with_mapping(original_text=original)

    assert result.speak_text != original
    assert len(result.speak_to_original) == len(result.speak_text)
    assert all(0 <= i < len(original) for i in result.speak_to_original)


def test_mapping_stays_in_bounds_for_symbols_the_sanitizer_rewrites():
    original = "10% & 20% of $5"
    mapper = SanitizedTextMapper()

    result = mapper.sanitize_with_mapping(original_text=original)

    assert len(result.speak_to_original) == len(result.speak_text)
    assert all(0 <= i < len(original) for i in result.speak_to_original)


def test_empty_input_maps_to_nothing():
    mapper = SanitizedTextMapper()

    result = mapper.sanitize_with_mapping(original_text="   ")

    assert result.speak_text == ""
    assert result.speak_to_original == []


# ---------------------------------------------------------------------------
# EstimatedAligner
# ---------------------------------------------------------------------------


def _mapping_for(text: str) -> list[int]:
    return list(range(len(text)))


def test_comma_and_clause_punctuation_lengthen_their_tokens():
    # A token ending in a comma should be given more of the audio than the same
    # token without one, because the speaker pauses there.
    aligner = EstimatedAligner()
    plain = "alpha alpha alpha"
    comma = "alpha, alpha alpha"

    plain_spans = aligner.estimate(
        chunk_id=0,
        speak_text=plain,
        speak_to_original=_mapping_for(plain),
        duration_ms=3000,
    ).spans
    comma_spans = aligner.estimate(
        chunk_id=0,
        speak_text=comma,
        speak_to_original=_mapping_for(comma),
        duration_ms=3000,
    ).spans

    plain_first = plain_spans[0].audio_end_ms - plain_spans[0].audio_start_ms
    comma_first = comma_spans[0].audio_end_ms - comma_spans[0].audio_start_ms
    assert comma_first > plain_first


def test_clause_punctuation_is_weighted_too():
    aligner = EstimatedAligner()
    text = "alpha: beta; gamma - delta"

    result = aligner.estimate(
        chunk_id=1,
        speak_text=text,
        speak_to_original=_mapping_for(text),
        duration_ms=4000,
    )

    assert result.spans
    assert result.spans[-1].audio_end_ms == 4000


def test_the_last_span_always_ends_exactly_at_the_duration():
    # Rounding per token otherwise leaves the final span short, which shows up
    # as highlighting that stops before the audio does.
    aligner = EstimatedAligner()
    text = "one two three four five six seven"

    result = aligner.estimate(
        chunk_id=2,
        speak_text=text,
        speak_to_original=_mapping_for(text),
        duration_ms=3333,
    )

    assert result.spans[-1].audio_end_ms == 3333


def test_tokens_beyond_the_mapping_are_skipped():
    # A mapping shorter than the spoken text must not index out of range.
    aligner = EstimatedAligner()
    text = "alpha beta gamma delta"

    result = aligner.estimate(
        chunk_id=3,
        speak_text=text,
        speak_to_original=_mapping_for("alpha")[:5],
        duration_ms=1000,
    )

    assert all(span.end_char <= 5 for span in result.spans)


def test_a_token_whose_mapping_collapses_is_dropped():
    # When the mapping runs backwards across a token, start and end resolve to
    # the same character and the span would be zero width.
    aligner = EstimatedAligner()
    text = "ab cd"

    result = aligner.estimate(
        chunk_id=4,
        speak_text=text,
        speak_to_original=[5, 4, 3, 2, 1],
        duration_ms=1000,
    )

    assert all(span.end_char > span.start_char for span in result.spans)


def test_no_mapping_at_all_yields_no_spans():
    aligner = EstimatedAligner()

    result = aligner.estimate(
        chunk_id=5, speak_text="alpha beta", speak_to_original=[], duration_ms=1000
    )

    assert result.spans == []


def test_empty_text_or_zero_duration_yields_no_spans():
    aligner = EstimatedAligner()

    assert (
        aligner.estimate(
            chunk_id=6, speak_text="   ", speak_to_original=[], duration_ms=1000
        ).spans
        == []
    )
    assert (
        aligner.estimate(
            chunk_id=7, speak_text="alpha", speak_to_original=[0], duration_ms=0
        ).spans
        == []
    )
