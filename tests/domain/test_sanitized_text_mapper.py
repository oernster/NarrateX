from __future__ import annotations

from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper
from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer


def test_sanitized_text_mapper_returns_mapping_with_same_length_as_speak_text() -> None:
    m = SanitizedTextMapper()
    original = "1.2 Introduction\nHello   world..."
    out = m.sanitize_with_mapping(original_text=original)
    assert isinstance(out.speak_text, str)
    assert len(out.speak_to_original) == len(out.speak_text)
    if out.speak_text:
        assert min(out.speak_to_original) >= 0
        assert max(out.speak_to_original) < len(original)


def test_words_said_for_a_symbol_stay_on_the_symbol_and_the_rest_realigns() -> None:
    """Measured on 2026-11-04: a scan ran ahead and mapped every word after a
    formula to the chunk's last character. An alignment does not."""

    original = "a ≥ b, then c."
    out = SanitizedTextMapper().sanitize_with_mapping(original_text=original)

    assert out.speak_text == "a greater than or equal to b, then c."
    said_for_symbol = out.speak_text.index("greater")
    assert out.speak_to_original[said_for_symbol] == original.index(" ")
    assert out.speak_to_original[out.speak_text.index("then")] == original.index("then")
    assert out.speak_to_original[-1] == len(original) - 1


def test_spoken_text_before_any_match_maps_to_the_first_match(monkeypatch) -> None:
    monkeypatch.setattr(SpokenTextSanitizer, "sanitize", lambda self, txt: "zz hello")

    out = SanitizedTextMapper().sanitize_with_mapping(original_text="hello")

    assert out.speak_to_original == [0, 0, 0, 0, 1, 2, 3, 4]


def test_spoken_text_matching_nothing_maps_to_the_start(monkeypatch) -> None:
    monkeypatch.setattr(SpokenTextSanitizer, "sanitize", lambda self, txt: "zz")

    out = SanitizedTextMapper().sanitize_with_mapping(original_text="hello")

    assert out.speak_to_original == [0, 0]
