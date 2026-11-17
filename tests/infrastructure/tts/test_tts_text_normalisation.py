"""What the Kokoro engine rewrites before misaki sees the text.

Every case here was measured through misaki 0.7.4: a plain hyphen between
spaces is tagged HYPH, goes to the espeak fallback, comes back silent and makes
phonemizer warn of a word count mismatch; a spaced em dash is tagged as
punctuation and spoken as a pause. A zero-width space and a link's scheme also
reached espeak, which could not say them.
"""

from __future__ import annotations

import pytest

from voice_reader.infrastructure.tts.kokoro_engine import _normalise_for_tts


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        (
            "an existing structure - tracking metrics",
            "an existing structure \u2014 tracking metrics",
        ),
        ("structure\u2014tracking", "structure \u2014 tracking"),
        ("x \u2013 y", "x \u2014 y"),
        ("2020\u20132026", "2020 \u2014 2026"),
    ],
    ids=["spaced-hyphen", "em-dash", "en-dash", "range"],
)
def test_every_dash_is_spoken_as_a_spaced_em_dash(text: str, spoken: str) -> None:
    assert _normalise_for_tts(text) == spoken


@pytest.mark.parametrize(
    "text",
    ["well-known co-op", "minus -5", "555-1234", "end -"],
)
def test_a_hyphen_that_is_not_a_dash_is_left_alone(text: str) -> None:
    assert _normalise_for_tts(text) == text


def test_invisible_characters_are_removed() -> None:
    assert _normalise_for_tts("​Title⁠ here﻿") == "Title here"


def test_a_link_is_read_without_its_scheme() -> None:
    assert (
        _normalise_for_tts("at https://www.crankthecode.com and http://a.org")
        == "at www.crankthecode.com and a.org"
    )
