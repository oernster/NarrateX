"""Domain dotted-leader detection, including the empty-input guard."""

from __future__ import annotations

import pytest

from voice_reader.domain.text_patterns import contains_dotted_leader


@pytest.mark.parametrize("text", ["", "   ", "\t\n", None])
def test_blank_or_missing_text_has_no_leader(text) -> None:
    assert contains_dotted_leader(text) is False


@pytest.mark.parametrize(
    "text",
    ["Chapter 1 .... 12", "Chapter 1 . . . . 12", "Chapter 1 ·· 12"],
)
def test_leader_forms_are_detected(text: str) -> None:
    assert contains_dotted_leader(text) is True


def test_ordinary_punctuation_is_not_a_leader() -> None:
    assert contains_dotted_leader("It ended. Then it began.") is False
