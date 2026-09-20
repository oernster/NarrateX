"""A blockquote that is most of a book is indentation, not quotation."""

from __future__ import annotations

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.structural_quotes import (
    as_ordinary_paragraphs,
    quotes_are_structural,
)


def _quotes(n: int) -> list[BlockDraft]:
    return [BlockDraft(kind=BlockKind.BLOCK_QUOTE, text=f"q{i}") for i in range(n)]


def _paragraphs(n: int) -> list[BlockDraft]:
    return [BlockDraft(kind=BlockKind.PARAGRAPH, text=f"p{i}") for i in range(n)]


def test_a_book_that_is_mostly_quoted_is_indented_rather_than_quoting() -> None:
    """Measured: a Kindle conversion came out 3450 quotes to 126 paragraphs."""

    drafts = _quotes(3450) + _paragraphs(126)

    assert quotes_are_structural(drafts) is True


def test_a_novel_quoting_a_letter_is_still_quoting() -> None:
    """Measured: the worst real book in the library is 20 against 3516."""

    drafts = _quotes(20) + _paragraphs(3516)

    assert quotes_are_structural(drafts) is False


def test_an_equal_split_is_left_alone() -> None:
    """The comparison is strict, so a tie keeps the author's markup."""

    assert quotes_are_structural(_quotes(5) + _paragraphs(5)) is False


def test_a_book_with_no_blocks_at_all_claims_nothing() -> None:
    assert quotes_are_structural([]) is False
    assert as_ordinary_paragraphs([]) == []


def test_a_structural_quote_becomes_a_paragraph_and_keeps_its_words() -> None:
    drafts = [
        BlockDraft(kind=BlockKind.BLOCK_QUOTE, text="The wind rose.", level=2),
        BlockDraft(kind=BlockKind.HEADING, text="One", level=1),
    ]

    out = as_ordinary_paragraphs(drafts)

    assert [d.kind for d in out] == [BlockKind.PARAGRAPH, BlockKind.HEADING]
    assert out[0].text == "The wind rose."
    assert out[0].level == 2


def test_a_genuine_quote_is_handed_back_untouched() -> None:
    drafts = _quotes(1) + _paragraphs(9)

    assert as_ordinary_paragraphs(drafts) == list(drafts)
