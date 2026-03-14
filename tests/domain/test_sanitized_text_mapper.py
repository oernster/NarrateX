from __future__ import annotations

from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper


def test_sanitized_text_mapper_returns_mapping_with_same_length_as_speak_text() -> None:
    m = SanitizedTextMapper()
    original = "1.2 Introduction\nHello   world..."
    out = m.sanitize_with_mapping(original_text=original)
    assert isinstance(out.speak_text, str)
    assert len(out.speak_to_original) == len(out.speak_text)
    if out.speak_text:
        assert min(out.speak_to_original) >= 0
        assert max(out.speak_to_original) < len(original)

