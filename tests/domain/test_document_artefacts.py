"""Tests for text-only artefact detection."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.artefacts import (
    is_artefact,
    is_contents_entry,
    is_folio,
)


class TestFolios:
    @pytest.mark.parametrize(
        "text",
        [
            "12",
            "  7  ",
            "- 12 -",
            "[42]",
            "xiv",
            "XIV",
            "iv",
            "Page 12",
            "page 3",
        ],
    )
    def test_recognises_page_numbers(self, text: str) -> None:
        assert is_folio(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "Chapter 1 begins here",
            "12345",
            "The year 1984 mattered",
            "3.14159 is pi",
        ],
    )
    def test_rejects_prose_and_long_numbers(self, text: str) -> None:
        assert is_folio(text) is False

    def test_a_five_digit_run_is_not_a_folio(self) -> None:
        # Four digits is the ceiling; beyond that it is data, not a page.
        assert is_folio("10000") is False
        assert is_folio("9999") is True


class TestContentsEntries:
    @pytest.mark.parametrize(
        "text",
        [
            "Prologue ..... 23",
            "Prologue . . . . . . 2",
            "Chapter One .......... xiv",
            "The Long Chapter Title...7",
        ],
    )
    def test_recognises_dotted_leader_entries(self, text: str) -> None:
        assert is_contents_entry(text) is True

    def test_a_long_leader_alone_is_an_entry(self) -> None:
        # Observed in the real hardback: a two-column contents page extracts
        # the titles and the page numbers as separate lines, so the entry
        # arrives with no number attached to it.
        assert is_contents_entry("Prologue . . . . . . . . . . . .") is True

    def test_a_short_leader_still_needs_a_page_number(self) -> None:
        assert is_contents_entry("Trailing off...") is False

    def test_requires_a_leader(self) -> None:
        assert is_contents_entry("Prologue 23") is False

    def test_prose_with_an_ellipsis_is_not_an_entry(self) -> None:
        # Three dots is punctuation; a leader is a run of them.
        assert is_contents_entry("He paused... then left") is False
        assert is_contents_entry("She hesitated...") is False

    @pytest.mark.parametrize("text", ["", "   "])
    def test_empty_input_is_not_an_entry(self, text: str) -> None:
        assert is_contents_entry(text) is False


class TestIsArtefact:
    def test_a_folio_is_an_artefact(self) -> None:
        assert is_artefact("12") is True

    def test_a_contents_entry_is_an_artefact(self) -> None:
        assert is_artefact("Prologue ..... 23") is True

    def test_prose_is_not_an_artefact(self) -> None:
        assert is_artefact("It was a bright cold day in April.") is False
