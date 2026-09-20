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


def test_sanitizer_expands_only_the_initialisms_the_author_marked() -> None:
    s = SpokenTextSanitizer()

    out = s.sanitize("I'm a CTO-level leader working with APIs in the U.K.")

    # The stops say the author meant letters, so the letters are spoken.
    assert "U K" in out
    # Nothing else is touched: a run of capitals cannot be told from emphasis.
    assert "CTO-level" in out
    assert "APIs" in out


def test_sanitizer_leaves_shouted_prose_as_words() -> None:
    """A novel's capitals are emphasis, never an initialism.

    Measured over `When the Wind Blows`: spelling capitals out fired 504 times
    and was wrong for roughly 86% of them, so a reader heard "P L E A S E".
    """

    s = SpokenTextSanitizer()

    assert s.sanitize("SOMEBODY PLEASE help me!") == "SOMEBODY PLEASE help me!"
    assert s.sanitize("FIRST FLIGHT") == "FIRST FLIGHT"
    assert s.sanitize("MAX! The FBI is here.") == "MAX! The FBI is here."


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
    # The dash characters are written as escapes rather than typed: they
    # are the input under test; a literal one in the file would be a dash
    # sitting in the repository.
    rule = "\u2014" * 3
    text = f"A\n\n{rule}\n\nB\n\n___\n\nC\n\n***\n\nD"
    out = s.sanitize(text)
    assert "A" in out
    assert "B" in out
    assert "C" in out
    assert "D" in out
    assert "\u2014" not in out
    assert "___" not in out
    assert "***" not in out
