from __future__ import annotations

from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper
from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer


def test_sanitized_text_mapper_empty_speak_returns_empty_mapping(monkeypatch) -> None:
    # Patch the sanitizer method at the class level (instances use slots and do
    # not allow setting methods as instance attributes).
    monkeypatch.setattr(SpokenTextSanitizer, "sanitize", lambda self, txt: "")
    mapper = SanitizedTextMapper()

    out = mapper.sanitize_with_mapping(original_text="Hello")
    assert out.speak_text == ""
    assert out.speak_to_original == []


def test_sanitized_text_mapper_space_at_end_maps_to_last_original_char(
    monkeypatch,
) -> None:
    # Force sanitized text to end with a space while original has no whitespace.
    monkeypatch.setattr(SpokenTextSanitizer, "sanitize", lambda self, txt: "Hi ")
    mapper = SanitizedTextMapper()

    out = mapper.sanitize_with_mapping(original_text="Hi")
    assert out.speak_text == "Hi "
    # The trailing space can't find whitespace in original, so it should map to last char.
    assert out.speak_to_original[-1] == 1


def test_sanitized_text_mapper_case_insensitive_fallback(monkeypatch) -> None:
    monkeypatch.setattr(SpokenTextSanitizer, "sanitize", lambda self, txt: "HELLO")
    mapper = SanitizedTextMapper()

    out = mapper.sanitize_with_mapping(original_text="hello")
    assert out.speak_text == "HELLO"
    # All chars should map within range.
    assert all(0 <= i < len("hello") for i in out.speak_to_original)
