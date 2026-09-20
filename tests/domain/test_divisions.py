"""The words a book divides itself with; how it numbers them."""

from __future__ import annotations

import pytest

from voice_reader.domain.document import divisions


@pytest.mark.parametrize(
    "text",
    [
        "Chapter 12",
        "CHAPTER 1",
        "Part II",
        "PART I",
        "Book Three",
        "PART THE FIRST",
        "CHAPTER TWENTY -",
        "CHAPTER ONE - Spaceguard",
        "Section 4.2",
        "Appendix 2",
        "volume iv",
        "Chapter the Last",
    ],
)
def test_a_numbered_division_is_recognised(text: str) -> None:
    assert divisions.is_numbered_division(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Book design by Virginia Norey",
        "Booking a table",
        "Chapter",
        "The chapter he wrote",
        "",
        "   ",
    ],
)
def test_a_division_word_without_a_number_is_prose(text: str) -> None:
    """Measured: "Book design by Virginia Norey" was the one false heading."""

    assert divisions.is_numbered_division(text) is False


def test_a_leading_division_word_is_seen_whether_numbered_or_not() -> None:
    assert divisions.opens_with_a_division_word("Book design by Norey") is True
    assert divisions.opens_with_a_division_word("Fencing Practice") is False


def test_a_named_division_matches_the_whole_text_only() -> None:
    words = divisions.FRONT_OPENINGS

    assert divisions.is_named_division("Prologue", words=words) is True
    assert divisions.is_named_division("prologue.", words=words) is True
    assert divisions.is_named_division("  FOREWORD ", words=words) is True
    assert divisions.is_named_division("Prologue to the war", words=words) is False
    assert divisions.is_named_division(None, words=words) is False


def test_an_epilogue_is_a_division_but_never_an_opening() -> None:
    """A book does not begin at its epilogue, so the two sets stay apart."""

    assert "epilogue" in divisions.OTHER_DIVISIONS
    assert "epilogue" not in divisions.FRONT_OPENINGS
