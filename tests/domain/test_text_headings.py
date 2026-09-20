"""Chapter headings recognised from the words, for a book that states none."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.text_headings import (
    as_text_headings,
    reads_as_a_heading,
)


def _para(text: str) -> BlockDraft:
    return BlockDraft(kind=BlockKind.PARAGRAPH, text=text)


@pytest.mark.parametrize(
    "text",
    ["Chapter 1", "PART I", "PART THE FIRST", "PROLOGUE", "Epilogue", "Interlude"],
)
def test_a_division_reads_as_a_heading(text: str) -> None:
    assert reads_as_a_heading(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Book design by Virginia Norey",
        "Fencing Practice",
        "The Good Man",
        "He opened chapter twelve and began to read it",
        "",
    ],
)
def test_prose_does_not_read_as_a_heading(text: str) -> None:
    """A prose-named chapter is beyond any rule reading words alone."""

    assert reads_as_a_heading(text) is False


def test_a_long_line_is_a_sentence_however_it_opens() -> None:
    """Measured: 540 of 544 real headings are six words or fewer."""

    assert reads_as_a_heading("Chapter 1 was the longest one he had ever read") is False


def test_the_divisions_found_become_headings() -> None:
    drafts = [_para("Chapter 1"), _para("The wind rose."), _para("Chapter 2")]

    out = as_text_headings(drafts)

    assert [d.kind for d in out] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
    ]
    assert out[0].level == 1


def test_a_book_that_already_has_a_heading_is_untouched() -> None:
    """The last fallback: it never overrides the two above it."""

    drafts = [
        BlockDraft(kind=BlockKind.HEADING, text="One", level=2),
        _para("Chapter 1"),
        _para("Chapter 2"),
    ]

    assert as_text_headings(drafts) == list(drafts)


def test_one_division_alone_is_no_spine() -> None:
    drafts = [_para("Chapter 1"), _para("The wind rose.")]

    assert as_text_headings(drafts) == list(drafts)


def test_a_contents_entry_is_never_promoted() -> None:
    drafts = [
        BlockDraft(kind=BlockKind.TOC_ENTRY, text="Chapter 1"),
        BlockDraft(kind=BlockKind.TOC_ENTRY, text="Chapter 2"),
    ]

    assert as_text_headings(drafts) == list(drafts)


def test_a_book_with_no_divisions_at_all_is_left_alone() -> None:
    drafts = [_para("The wind rose."), _para("She ran.")]

    assert as_text_headings(drafts) == list(drafts)


def test_two_blocks_with_the_same_words_are_both_promoted() -> None:
    """Identity, not text: a repeated heading must not promote only one."""

    drafts = [_para("Chapter 1"), _para("Chapter 1")]

    out = as_text_headings(drafts)

    assert [d.kind for d in out] == [BlockKind.HEADING, BlockKind.HEADING]
