"""Tests for recognising the back-of-book index in a PDF.

The index is shown but never read aloud. "latency, 60, 189, 220" is
navigation, and the page says so itself, which is better evidence than the
shape of its lines: an index entry and a wrapped body line ending in a year
are hard to tell apart on text alone.
"""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.pdf_lines import (
    PdfLine,
    drafts_from_lines,
    index_pages,
)

PAGE_HEIGHT = 800.0
BODY_SIZE = 10.0
HEADING_SIZE = BODY_SIZE * 2
MIDDLE = 400.0
MARGIN = 10.0


def _line(
    text: str,
    *,
    size: float = BODY_SIZE,
    top: float = MIDDLE,
    page: int = 0,
    block: int = 0,
) -> PdfLine:
    return PdfLine(
        text=text,
        size=size,
        bold=False,
        top=top,
        bottom=top + size,
        page_index=page,
        page_height=PAGE_HEIGHT,
        block_index=block,
    )


def _body_filler(*, page: int, block: int) -> PdfLine:
    """Enough body-sized text that `body_size` settles on the body size."""

    return _line("A sentence of ordinary body prose. " * 4, page=page, block=block)


class TestFindingIndexPages:
    def test_a_running_head_in_the_margin_marks_the_page(self) -> None:
        lines = (
            _line("Index", top=MARGIN, page=7),
            _line("latency, 60, 189", page=7, block=1),
        )

        assert index_pages(lines, body=BODY_SIZE) == frozenset({7})

    def test_a_title_marks_the_opening_page_that_has_no_running_head(self) -> None:
        # The first index page carries the word as a title instead, which is
        # why looking only in the margin always misses it.
        lines = (
            _line("Index", size=HEADING_SIZE, page=7),
            _line("authority, 355", page=7, block=1),
        )

        assert index_pages(lines, body=BODY_SIZE) == frozenset({7})

    def test_a_two_page_index_is_found_without_any_repetition(self) -> None:
        # Most indexes are two pages, below the bar a generic running head has
        # to clear before it reads as furniture.
        lines = (
            _line("Index", top=MARGIN, page=7),
            _line("Index", top=MARGIN, page=8),
        )

        assert index_pages(lines, body=BODY_SIZE) == frozenset({7, 8})

    def test_a_named_index_variant_is_recognised(self) -> None:
        lines = (_line("Subject Index", top=MARGIN, page=2),)

        assert index_pages(lines, body=BODY_SIZE) == frozenset({2})

    def test_the_word_in_body_text_does_not_mark_the_page(self) -> None:
        # Mid-page and body-sized, so it is prose that happens to say "index".
        lines = (_line("Index", page=7),)

        assert index_pages(lines, body=BODY_SIZE) == frozenset()

    def test_a_book_with_no_index_marks_nothing(self) -> None:
        lines = (_body_filler(page=0, block=0),)

        assert index_pages(lines, body=BODY_SIZE) == frozenset()


class TestClassifyingIndexLines:
    def test_index_lines_are_displayed_but_not_spoken(self) -> None:
        lines = (
            _body_filler(page=0, block=0),
            _line("Index", top=MARGIN, page=3),
            _line("latency, 60, 189, 220", page=3, block=1),
        )

        drafts = drafts_from_lines(lines)
        entries = [d for d in drafts if d.kind is BlockKind.INDEX_ENTRY]

        assert "latency, 60, 189, 220" in [d.text for d in entries]
        # The word "Index" itself is furniture too, not something to read out.
        assert not any(
            d.kind is BlockKind.PARAGRAPH and "latency" in d.text for d in drafts
        )
        assert BlockKind.INDEX_ENTRY.is_displayed
        assert not BlockKind.INDEX_ENTRY.is_spoken

    def test_a_heading_on_an_index_page_is_still_a_heading(self) -> None:
        lines = (
            _body_filler(page=0, block=0),
            _line("Index", top=MARGIN, page=3),
            _line("Symbols", size=HEADING_SIZE, page=3, block=1),
        )

        drafts = drafts_from_lines(lines)

        assert any(d.kind is BlockKind.HEADING and d.text == "Symbols" for d in drafts)

    def test_body_pages_are_untouched_by_an_index_elsewhere(self) -> None:
        lines = (
            _line("Real body prose that should still be spoken.", page=0),
            _line("Index", top=MARGIN, page=3),
            _line("latency, 60", page=3, block=1),
        )

        drafts = drafts_from_lines(lines)

        assert any(
            d.kind is BlockKind.PARAGRAPH and "still be spoken" in d.text
            for d in drafts
        )
