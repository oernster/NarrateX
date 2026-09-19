"""The three filename conventions the reference library actually uses.

Each count below was measured over H:/Books on 2026-09-19, so each test stands
for a real block of the library rather than for an invented edge case.
"""

from __future__ import annotations

import pytest

from voice_reader.domain.shelf import text


@pytest.mark.parametrize(
    ("stem", "title", "author"),
    [
        # 296 files put the author first, in sort form.
        ("King, Stephen - From a Buick 8", "From a Buick 8", "Stephen King"),
        (
            "Cussler, Clive - Dirk Pitt 17 - Atlantis Found",
            "Dirk Pitt 17 - Atlantis Found",
            "Clive Cussler",
        ),
        ("Carlin, George - Last Words", "Last Words", "George Carlin"),
    ],
)
def test_an_author_stated_first_is_read_as_the_author(
    stem: str, title: str, author: str
) -> None:
    assert text.split_filename(stem) == (title, author)


def test_a_title_in_sort_form_is_not_mistaken_for_an_author() -> None:
    assert text.split_filename("Ambler Warning, The - Ludlum, Robert") == (
        "The Ambler Warning",
        "Robert Ludlum",
    )


def test_a_forename_beginning_with_an_article_is_still_an_author() -> None:
    """`An` opens `Andrew`, so the article test needs a word boundary."""

    assert text.split_filename("Smith, Andrew - Some Book") == (
        "Some Book",
        "Andrew Smith",
    )


def test_a_title_holding_an_underscore_is_never_read_as_a_name() -> None:
    assert text.split_filename("2001_ A Space Odyssey - Arthur C. Clarke") == (
        "2001: A Space Odyssey",
        "Arthur C. Clarke",
    )


@pytest.mark.parametrize(
    ("stem", "author"),
    [
        # 16 files separate co-authors with the same punctuation a sort name uses.
        (
            "Juggler of Worlds - Larry Niven_ Edward M. Lerner",
            "Larry Niven, Edward M. Lerner",
        ),
        (
            "Daughter of the Empire - Raymond E. Feist_ Janny Wurts",
            "Raymond E. Feist, Janny Wurts",
        ),
        # 28 files carry one author in sort form.
        ("Anansi Boys - Gaiman_ Neil", "Neil Gaiman"),
        ("NUMA 1 - Serpent - Cussler_ Clive", "Clive Cussler"),
    ],
)
def test_co_authors_are_kept_apart_from_a_sort_name(stem: str, author: str) -> None:
    assert text.split_filename(stem)[1] == author


@pytest.mark.parametrize(
    "stem",
    [
        "New Scientist - 19 April 2014",
        "New Scientist - 12 April 2014",
        "New Scientist - March 29 2014 UK",
    ],
)
def test_an_issue_date_is_not_an_author_and_stays_in_the_title(stem: str) -> None:
    title, author = text.split_filename(stem)
    assert author == text.UNKNOWN_AUTHOR
    assert title == text.display_title(stem)


def test_two_issues_of_one_magazine_stay_two_works() -> None:
    first = text.split_filename("New Scientist - 19 April 2014")
    second = text.split_filename("New Scientist - 12 April 2014")
    assert first != second


def test_a_year_in_a_title_is_not_a_date() -> None:
    assert text.split_filename("1984 - George Orwell") == ("1984", "George Orwell")


def test_a_month_name_without_a_number_is_not_a_date() -> None:
    assert text.split_filename("The Long Walk - May Sarton") == (
        "The Long Walk",
        "May Sarton",
    )


def test_a_name_too_long_to_be_a_surname_is_not_read_as_an_author() -> None:
    assert text.split_filename("Some Long Title Here, Ish - Actual Author") == (
        "Some Long Title Here, Ish",
        "Actual Author",
    )
