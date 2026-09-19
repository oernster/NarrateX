"""Title and author reading, against the shapes the reference library holds."""

from __future__ import annotations

import pytest

from voice_reader.domain.shelf import text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bachman Books, The", "The Bachman Books"),
        ("Ambler Warning, The", "The Ambler Warning"),
        ("2001_ A Space Odyssey", "2001: A Space Odyssey"),
        ("2010_ Odyssey Two", "2010: Odyssey Two"),
        ("Night Shift", "Night Shift"),
        ("  spaced   out  ", "spaced out"),
        ("Apprentice, the", "The Apprentice"),
    ],
)
def test_display_title(raw: str, expected: str) -> None:
    assert text.display_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Child, Lee", "Lee Child"),
        ("Gaiman_ Neil", "Neil Gaiman"),
        ("Ludlum, Robert", "Robert Ludlum"),
        ("Arthur C. Clarke", "Arthur C. Clarke"),
        ("Neil Gaiman (2)", "Neil Gaiman"),
    ],
)
def test_display_author(raw: str, expected: str) -> None:
    assert text.display_author(raw) == expected


def test_title_key_drops_the_article_wherever_it_sits() -> None:
    assert text.title_key("The Stand") == text.title_key("Stand, The")
    assert text.title_key("The Stand") == text.title_key("Stand")


def test_title_key_reads_an_underscore_as_a_colon() -> None:
    assert text.title_key("2010_ Odyssey Two") == text.title_key("2010 Odyssey Two")


def test_author_key_is_insensitive_to_order_and_punctuation() -> None:
    measured = ["Arthur C Clarke", "Arthur C. Clarke", "Clarke, Arthur C."]
    keys = {text.author_key(name) for name in measured}
    assert len(keys) == 1


def test_author_key_folds_accents() -> None:
    assert text.author_key("Émile Zola") == text.author_key("Emile Zola")


@pytest.mark.parametrize(
    ("stem", "title", "author"),
    [
        ("A Wanted Man - Child, Lee", "A Wanted Man", "Lee Child"),
        ("Anansi Boys - Gaiman_ Neil", "Anansi Boys", "Neil Gaiman"),
        ("American Gods - Neil Gaiman (2)", "American Gods", "Neil Gaiman"),
        ("Ambler Warning, The - Ludlum, Robert", "The Ambler Warning", "Robert Ludlum"),
        (
            "Blood Meridian - Or the Evening Redness - Cormac McCarthy",
            "Blood Meridian - Or the Evening Redness",
            "Cormac McCarthy",
        ),
    ],
)
def test_split_filename(stem: str, title: str, author: str) -> None:
    assert text.split_filename(stem) == (title, author)


def test_split_filename_without_a_separator_has_no_author() -> None:
    assert text.split_filename("book1") == ("book1", text.UNKNOWN_AUTHOR)


def test_split_filename_with_an_empty_title_keeps_the_whole_stem() -> None:
    assert text.split_filename(" - Lee Child") == ("- Lee Child", text.UNKNOWN_AUTHOR)


def test_split_filename_with_an_empty_author_reads_as_unknown() -> None:
    title, author = text.split_filename("A Wanted Man - ")
    assert (title, author) == ("A Wanted Man", text.UNKNOWN_AUTHOR)


@pytest.mark.parametrize(
    ("stem", "expected"),
    [("American Gods - Neil Gaiman (2)", 2), ("American Gods - Neil Gaiman", 1)],
)
def test_copy_number(stem: str, expected: int) -> None:
    assert text.copy_number(stem) == expected


def test_sort_key_orders_by_author_then_title() -> None:
    clarke = text.sort_key("Rama", "Arthur C. Clarke")
    koontz = text.sort_key("Anti-Man", "Dean R. Koontz")
    assert clarke < koontz


def test_sort_key_puts_an_unknown_author_last() -> None:
    known = text.sort_key("Rama", "Arthur C. Clarke")
    unknown = text.sort_key("Rama", text.UNKNOWN_AUTHOR)
    empty = text.sort_key("Rama", "  ")
    assert known < unknown
    assert known < empty
