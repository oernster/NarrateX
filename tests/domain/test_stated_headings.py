"""Headings taken from a book's own navigation, where it marks up none."""

from __future__ import annotations

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.stated_headings import (
    as_stated_headings,
    states_no_headings,
)

NAMES = ("Prologue", "Chapter 1", "Chapter 2")


def _para(text: str) -> BlockDraft:
    return BlockDraft(kind=BlockKind.PARAGRAPH, text=text)


def test_a_book_marking_up_nothing_states_no_headings() -> None:
    assert states_no_headings([_para("Chapter 1")]) is True


def test_one_heading_of_its_own_is_enough_to_count() -> None:
    drafts = [BlockDraft(kind=BlockKind.HEADING, text="One", level=1), _para("x")]

    assert states_no_headings(drafts) is False


def test_a_named_block_becomes_a_heading() -> None:
    drafts = [_para("Chapter 1"), _para("The wind rose."), _para("Chapter 2")]

    out = as_stated_headings(drafts, names=NAMES)

    assert [d.kind for d in out] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
    ]
    assert out[0].level == 1
    assert out[0].text == "Chapter 1"


def test_the_contents_copy_of_a_name_is_left_as_a_contents_entry() -> None:
    """Each name appears twice: in the contents and at the chapter itself."""

    drafts = [
        BlockDraft(kind=BlockKind.TOC_ENTRY, text="Chapter 1"),
        _para("Chapter 1"),
    ]

    out = as_stated_headings(drafts, names=NAMES)

    assert [d.kind for d in out] == [BlockKind.TOC_ENTRY, BlockKind.HEADING]


def test_a_book_with_its_own_headings_is_untouched() -> None:
    """A fallback, never an override: nothing that works today can change."""

    drafts = [
        BlockDraft(kind=BlockKind.HEADING, text="One", level=2),
        _para("Chapter 1"),
    ]

    assert as_stated_headings(drafts, names=NAMES) == list(drafts)


def test_a_navigation_of_one_name_is_no_spine() -> None:
    """Calibre leaves a single entry reading "Start" where there was no table."""

    drafts = [_para("Start"), _para("The wind rose.")]

    assert as_stated_headings(drafts, names=["Start"]) == list(drafts)


def test_a_navigation_of_nothing_at_all_changes_nothing() -> None:
    drafts = [_para("Chapter 1")]

    assert as_stated_headings(drafts, names=[]) == list(drafts)
    assert as_stated_headings(drafts, names=["", "   "]) == list(drafts)


def test_surrounding_whitespace_does_not_hide_a_name() -> None:
    drafts = [_para("  Chapter 1 "), _para("Chapter 2")]

    out = as_stated_headings(drafts, names=("Chapter 1 ", " Chapter 2"))

    assert all(d.kind is BlockKind.HEADING for d in out)


def test_prose_the_navigation_does_not_name_stays_prose() -> None:
    drafts = [_para("Chapter 1"), _para("Chapter 1 was a long one.")]

    out = as_stated_headings(drafts, names=NAMES)

    assert [d.kind for d in out] == [BlockKind.HEADING, BlockKind.PARAGRAPH]
