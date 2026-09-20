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


def test_a_book_that_states_no_title_can_still_show_a_header() -> None:
    """A text leading most of the documents is furniture on its own evidence.

    This used to answer None: the only condition was matching the stated
    title. A header that words the title differently was then missed, which is
    what left 93 of them in `Fang: A Maximum Ride Novel`.
    """

    assert running_header([TITLE, TITLE], title=None) == TITLE
    assert running_header([TITLE, TITLE], title="   ") == TITLE


def test_no_title_and_no_repeated_lead_finds_nothing() -> None:
    leads = [TITLE, "Prologue", "Chapter 1", "Chapter 2"]

    assert running_header(leads, title=None) is None


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


class TestAHeaderThatIsNotTheTitle:
    """Measured: `Fang: A Maximum Ride Novel` heads its pages differently.

    Its running header reads "Maximum Ride 6 - Fang" and leads 93 of the book's
    94 documents. Matching the stated title alone left all 93 in the text; the
    book's own navigation then named the header, so the shelf gained three
    sections called after it.
    """

    def test_a_lead_on_most_of_the_documents_is_furniture_whatever_it_says(
        self,
    ) -> None:
        leads = ["Maximum Ride 6 - Fang"] * 93 + ["Table of Contents"]

        assert (
            running_header(leads, title="Fang: A Maximum Ride Novel")
            == "Maximum Ride 6 - Fang"
        )

    def test_a_lead_on_a_few_documents_is_still_prose(self) -> None:
        """Measured: "Elsewhere," leads 2 of 64 documents and is a chapter."""

        leads = ["Elsewhere,"] * 2 + [f"chapter {n}" for n in range(62)]

        assert running_header(leads, title="Creation Node") is None

    def test_the_title_still_wins_where_it_leads_only_half(self) -> None:
        """`When the Wind Blows` leads 128 of 254; the title condition holds."""

        leads = [TITLE] * 3 + [f"chapter {n}" for n in range(40)]

        assert running_header(leads, title=TITLE) == TITLE

    def test_a_book_whose_documents_all_open_differently_has_no_header(self) -> None:
        leads = [f"chapter {n}" for n in range(40)]

        assert running_header(leads, title=TITLE) is None

    def test_blank_leads_are_not_a_header(self) -> None:
        assert running_header(["", "   "], title=TITLE) is None
