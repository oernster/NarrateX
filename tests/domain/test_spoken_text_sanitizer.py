from __future__ import annotations

from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer


def test_sanitizer_removes_number_only_lines_and_prefixes() -> None:
    text = "1\nIntroduction\n1.1\nAbout me\n1.1.1 Perspective\nHello there."
    s = SpokenTextSanitizer()
    out = s.sanitize(text)
    assert "1\n" not in out
    assert "1.1" not in out
    assert "Perspective" in out
    assert "Hello there." in out


def test_sanitizer_can_return_empty_for_number_only_text() -> None:
    s = SpokenTextSanitizer()
    out = s.sanitize("1\n1.1\n2\n")
    assert out == ""
