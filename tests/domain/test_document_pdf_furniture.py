"""Tests for detecting and stripping PDF page furniture.

Running heads and margin folios are classified from layout evidence, emit no
drafts (their text is stripped from the canonical source) and are reported
per page for the text extraction to remove.
"""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.pdf_lines import (
    PdfLine,
    drafts_from_lines,
    furniture_texts_by_page,
    running_head_keys,
)

PAGE_HEIGHT = 800.0
BODY_SIZE = 10.0
MIDDLE = 400.0


def _line(
    text: str,
    *,
    size: float = BODY_SIZE,
    bold: bool = False,
    top: float = MIDDLE,
    page: int = 0,
    block: int = 0,
) -> PdfLine:
    return PdfLine(
        text=text,
        size=size,
        bold=bold,
        top=top,
        bottom=top + size,
        page_index=page,
        page_height=PAGE_HEIGHT,
        block_index=block,
    )


class TestRunningHeads:
    def test_a_margin_line_repeating_across_pages_is_detected(self) -> None:
        lines = tuple(
            _line("A History of Everything", top=10.0, page=page) for page in range(4)
        )

        assert running_head_keys(lines) != frozenset()

    def test_two_pages_are_not_enough(self) -> None:
        lines = tuple(
            _line("A History of Everything", top=10.0, page=page) for page in range(2)
        )

        assert running_head_keys(lines) == frozenset()

    def test_repetition_ignores_the_changing_page_number(self) -> None:
        lines = tuple(
            _line(f"Chapter 3 | {40 + page}", top=10.0, page=page) for page in range(4)
        )

        assert running_head_keys(lines) != frozenset()

    def test_a_line_in_the_body_is_never_a_running_head(self) -> None:
        lines = tuple(
            _line("Repeated body phrase", top=MIDDLE, page=page) for page in range(5)
        )

        assert running_head_keys(lines) == frozenset()

    def test_a_line_with_no_letters_is_not_a_repetition_key(self) -> None:
        lines = tuple(_line("12", top=10.0, page=page) for page in range(5))

        assert running_head_keys(lines) == frozenset()

    def test_a_zero_height_page_has_no_margins(self) -> None:
        line = PdfLine(
            text="Header",
            size=BODY_SIZE,
            bold=False,
            top=0.0,
            bottom=10.0,
            page_index=0,
            page_height=0.0,
            block_index=0,
        )

        assert running_head_keys((line,) * 5) == frozenset()


class TestFurnitureEmitsNoDrafts:
    def test_a_standalone_page_number_in_the_margin_yields_no_draft(self) -> None:
        # The folio's text is stripped from the canonical source, so a draft
        # for it could only fail to anchor or steal a body occurrence.
        lines = (
            _line("A" * 200, block=0),
            _line("12", top=770.0, block=1),
        )
        drafts = drafts_from_lines(lines)

        assert [d.kind for d in drafts] == [BlockKind.PARAGRAPH]

    def test_a_repeated_margin_line_yields_no_draft(self) -> None:
        # Running heads are stripped from the canonical text, so no draft may
        # go looking for them.
        lines = tuple(
            _line("A History of Everything", top=10.0, page=page, block=0)
            for page in range(4)
        ) + (
            _line("A" * 200, page=4, block=1),
        )
        drafts = drafts_from_lines(lines)

        assert [d.kind for d in drafts] == [BlockKind.PARAGRAPH]

    def test_a_folio_still_interrupts_a_paragraph(self) -> None:
        # The folio emits no draft of its own, but it still breaks the run:
        # the prose either side of it was two blocks on the page.
        lines = (
            _line("Prose before the break.", block=0),
            _line("12", top=770.0, block=0),
            _line("Prose after the break.", block=0),
        )
        drafts = drafts_from_lines(lines)

        assert [d.kind for d in drafts] == [
            BlockKind.PARAGRAPH,
            BlockKind.PARAGRAPH,
        ]
        assert [d.text for d in drafts] == [
            "Prose before the break.",
            "Prose after the break.",
        ]

    def test_artefacts_are_neither_displayed_nor_spoken(self) -> None:
        lines = (
            _line("Prologue . . . . . . 2", block=0),
            _line("12", top=770.0, block=1),
        )
        for draft in drafts_from_lines(lines):
            assert draft.kind.is_displayed is False
            assert draft.kind.is_spoken is False


class TestFurnitureTexts:
    def test_no_lines_yields_no_furniture(self) -> None:
        assert furniture_texts_by_page(()) == {}

    def test_blank_lines_yield_no_furniture(self) -> None:
        assert furniture_texts_by_page((_line("  "), _line(""))) == {}

    def test_running_heads_and_margin_folios_are_selected_per_page(self) -> None:
        lines = tuple(
            _line("A History of Everything", top=10.0, page=page, block=0)
            for page in range(3)
        ) + tuple(
            _line(str(10 + page), top=770.0, page=page, block=1) for page in range(3)
        )

        assert furniture_texts_by_page(lines) == {
            0: ("A History of Everything", "10"),
            1: ("A History of Everything", "11"),
            2: ("A History of Everything", "12"),
        }

    def test_a_body_line_is_never_furniture(self) -> None:
        lines = tuple(
            _line("Repeated body phrase", top=MIDDLE, page=page) for page in range(5)
        )

        assert furniture_texts_by_page(lines) == {}

    def test_a_contents_column_number_is_not_furniture(self) -> None:
        # A reclassified contents-column number sits mid-page: it stays in the
        # text and keeps its draft, so it must not be stripped.
        lines = (
            _line("Prologue . . . . . . . . . . . .", block=0),
            _line("2", top=MIDDLE, block=1),
        )

        assert furniture_texts_by_page(lines) == {}

    def test_a_dotted_contents_entry_in_the_margin_is_not_furniture(self) -> None:
        # A contents entry reads as a contents entry before anything else,
        # even when it sits in the margin band.
        lines = tuple(
            _line("Prologue . . . . . . 2", top=10.0, page=page) for page in range(3)
        )

        assert furniture_texts_by_page(lines) == {}

    def test_selected_furniture_matches_the_drafts_that_vanish(self) -> None:
        # The two consumers must agree: every line selected for stripping is
        # exactly a line that emits no draft.
        lines = tuple(
            _line("A History of Everything", top=10.0, page=page, block=0)
            for page in range(3)
        ) + (
            _line("Body prose that stays.", page=0, block=1),
            _line("12", top=770.0, page=0, block=2),
        )

        furniture = furniture_texts_by_page(lines)
        drafts = drafts_from_lines(lines)

        assert furniture == {
            0: ("A History of Everything", "12"),
            1: ("A History of Everything",),
            2: ("A History of Everything",),
        }
        assert [d.text for d in drafts] == ["Body prose that stays."]
