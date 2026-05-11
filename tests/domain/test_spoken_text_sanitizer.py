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
    assert "\n" not in out


def test_sanitizer_expands_acronyms() -> None:
    s = SpokenTextSanitizer()
    out = s.sanitize("I'm a CTO-level leader working with APIs in the U.K.")
    # Keep words but expand initialisms for TTS.
    assert "C T O" in out
    assert "A P I" in out
    assert "U K" in out


def test_sanitizer_can_return_empty_for_number_only_text() -> None:
    s = SpokenTextSanitizer()
    out = s.sanitize("1\n1.1\n2\n")
    assert out == ""


def test_sanitizer_drops_separator_only_lines() -> None:
    s = SpokenTextSanitizer()
    text = "Before\n\n---\n\nAfter"
    out = s.sanitize(text)
    assert "---" not in out
    assert "Before" in out
    assert "After" in out


def test_sanitizer_drops_unicode_dash_separators_and_common_rules() -> None:
    s = SpokenTextSanitizer()
    # Em dash / en dash / minus sign + common horizontal rules.
    text = "A\n\n———\n\nB\n\n___\n\nC\n\n***\n\nD"
    out = s.sanitize(text)
    assert "A" in out
    assert "B" in out
    assert "C" in out
    assert "D" in out
    assert "—" not in out
    assert "___" not in out
    assert "***" not in out
