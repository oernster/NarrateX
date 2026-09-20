"""Telling page furniture from prose that happens to repeat."""

from __future__ import annotations

from voice_reader.domain.document.running_headers import (
    running_header,
    without_header,
)

TITLE = "When the Wind Blows"


def test_a_title_leading_several_documents_is_furniture() -> None:
    leads = [TITLE, TITLE, "Prologue", TITLE]

    assert running_header(leads, title=TITLE) == TITLE


def test_a_title_page_on_its_own_is_left_alone() -> None:
    """One lead is a title page; furniture runs through the book."""

    assert running_header([TITLE, "Prologue", "Chapter 1"], title=TITLE) is None


def test_a_repeated_lead_that_is_not_the_title_is_prose() -> None:
    """Measured: "Elsewhere," and "Chapter 11" both lead two documents."""

    leads = ["Elsewhere,", "Elsewhere,", "Chapter 11", "Chapter 11"]

    assert running_header(leads, title=TITLE) is None


def test_a_book_that_states_no_title_has_no_furniture_to_find() -> None:
    assert running_header([TITLE, TITLE], title=None) is None
    assert running_header([TITLE, TITLE], title="   ") is None


def test_surrounding_whitespace_does_not_hide_the_header() -> None:
    assert running_header([f"  {TITLE} ", TITLE], title=f" {TITLE}  ") == TITLE


def test_every_line_that_is_only_the_header_goes() -> None:
    lines = [TITLE, "Prologue", f" {TITLE} ", "The wind rose."]

    assert without_header(lines, header=TITLE) == ["Prologue", "The wind rose."]


def test_a_sentence_containing_the_title_is_prose_and_stays() -> None:
    lines = [f"It was called {TITLE}, she remembered."]

    assert without_header(lines, header=TITLE) == lines


def test_no_header_leaves_every_line_where_it_was() -> None:
    lines = [TITLE, "Prologue"]

    assert without_header(lines, header=None) == lines
