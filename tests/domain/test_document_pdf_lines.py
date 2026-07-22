"""Tests for classifying PDF lines into blocks."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.pdf_lines import (
    PdfLine,
    body_size,
    drafts_from_lines,
    join_paragraph_lines,
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


class TestBodySize:
    def test_no_lines_yields_zero(self) -> None:
        assert body_size(()) == 0.0

    def test_blank_lines_are_ignored(self) -> None:
        assert body_size((_line("   "),)) == 0.0

    def test_the_dominant_size_wins_by_volume_of_text(self) -> None:
        lines = (
            _line("A short heading", size=24.0),
            _line("A" * 200, size=10.0),
            _line("B" * 200, size=10.0),
        )

        assert body_size(lines) == 10.0

    def test_a_tie_prefers_the_larger_size(self) -> None:
        lines = (_line("AAAA", size=10.0), _line("BBBB", size=12.0))

        assert body_size(lines) == 12.0


class TestClassification:
    def test_no_lines_yields_no_drafts(self) -> None:
        assert drafts_from_lines(()) == ()

    def test_blank_lines_yield_no_drafts(self) -> None:
        assert drafts_from_lines((_line("  "), _line(""))) == ()

    def test_larger_text_becomes_a_heading(self) -> None:
        lines = (
            _line("Chapter One", size=18.0),
            _line("A" * 200, size=BODY_SIZE, block=1),
        )
        drafts = drafts_from_lines(lines)

        assert drafts[0].kind is BlockKind.HEADING
        assert drafts[0].text == "Chapter One"

    def test_bold_text_at_body_size_still_reads_as_a_heading(self) -> None:
        lines = (
            _line("Chapter One", bold=True),
            _line("A" * 200, block=1),
        )

        assert drafts_from_lines(lines)[0].kind is BlockKind.HEADING

    def test_a_long_run_of_large_text_is_not_a_heading(self) -> None:
        lines = (
            _line(" ".join(["word"] * 30), size=18.0),
            _line("A" * 200, block=1),
        )

        assert drafts_from_lines(lines)[0].kind is BlockKind.PARAGRAPH

    def test_heading_levels_rank_by_size(self) -> None:
        lines = (
            _line("Part One", size=24.0, block=0),
            _line("Chapter One", size=18.0, block=1),
            _line("A Subsection", size=14.0, block=2),
            _line("A" * 300, block=3),
        )
        headings = [d for d in drafts_from_lines(lines) if d.kind is BlockKind.HEADING]

        assert [(h.text, h.level) for h in headings] == [
            ("Part One", 1),
            ("Chapter One", 2),
            ("A Subsection", 3),
        ]

    def test_a_number_in_the_body_is_not_a_folio(self) -> None:
        lines = (_line("A" * 200, block=0), _line("12", top=MIDDLE, block=1))
        drafts = drafts_from_lines(lines)

        assert all(d.kind is not BlockKind.PAGE_NUMBER for d in drafts)

    def test_a_dotted_leader_line_is_a_contents_entry(self) -> None:
        lines = (_line("Prologue . . . . . . 2"), _line("A" * 200, block=1))
        drafts = drafts_from_lines(lines)

        assert drafts[0].kind is BlockKind.TOC_ENTRY


class TestParagraphMerging:
    def test_lines_in_one_grouping_join_into_a_paragraph(self) -> None:
        lines = (
            _line("This sentence was", block=0),
            _line("split across three", block=0),
            _line("separate lines.", block=0),
        )
        drafts = drafts_from_lines(lines)

        assert len(drafts) == 1
        assert drafts[0].text == "This sentence was split across three separate lines."

    def test_a_new_grouping_starts_a_new_paragraph(self) -> None:
        lines = (
            _line("First paragraph.", block=0),
            _line("Second paragraph.", block=1),
        )
        drafts = drafts_from_lines(lines)

        assert [d.text for d in drafts] == ["First paragraph.", "Second paragraph."]

    def test_a_heading_interrupts_a_paragraph(self) -> None:
        lines = (
            _line("Trailing prose.", block=0),
            _line("Chapter Two", size=18.0, block=0),
            _line("Following prose.", block=0),
        )
        drafts = drafts_from_lines(lines)

        assert [d.kind for d in drafts] == [
            BlockKind.PARAGRAPH,
            BlockKind.HEADING,
            BlockKind.PARAGRAPH,
        ]

    def test_a_paragraph_continues_across_a_page_boundary(self) -> None:
        # Same grouping index on the next page still means one paragraph, which
        # is what a paragraph broken by a page turn looks like.
        lines = (
            _line("A sentence that runs", page=0, block=0),
            _line("onto the next page.", page=0, block=0),
        )
        drafts = drafts_from_lines(lines)

        assert len(drafts) == 1


class TestJoiningWrappedLines:
    def test_a_word_split_across_lines_is_healed(self) -> None:
        lines = (
            _line("It was a deci-", block=0),
            _line("sion he regretted.", block=0),
        )

        assert drafts_from_lines(lines)[0].text == "It was a decision he regretted."

    def test_a_genuine_compound_at_a_line_end_is_preserved(self) -> None:
        # An uppercase continuation means the hyphen belongs to the text.
        lines = (
            _line("the Anglo-", block=0),
            _line("Saxon period", block=0),
        )

        assert drafts_from_lines(lines)[0].text == "the Anglo- Saxon period"

    def test_blank_parts_are_skipped_when_joining(self) -> None:
        lines = (
            _line("First half", block=0),
            _line("   ", block=0),
            _line("second half.", block=0),
        )

        assert drafts_from_lines(lines)[0].text == "First half second half."

    def test_joining_an_empty_run_yields_nothing(self) -> None:
        assert join_paragraph_lines(()) == ""


class TestContentsPages:
    def test_a_bare_number_beside_a_contents_entry_is_a_page_number(self) -> None:
        # A two-column contents page extracts as alternating titles and page
        # numbers, so the numbers sit mid-page rather than in the margin.
        lines = (
            _line("Prologue . . . . . . . . . . . .", block=0),
            _line("2", top=MIDDLE, block=1),
            _line("Introduction . . . . . . . . . .", block=2),
            _line("5", top=MIDDLE, block=3),
        )
        drafts = drafts_from_lines(lines)

        assert [d.kind for d in drafts] == [
            BlockKind.TOC_ENTRY,
            BlockKind.PAGE_NUMBER,
            BlockKind.TOC_ENTRY,
            BlockKind.PAGE_NUMBER,
        ]

    def test_none_of_a_contents_page_is_spoken(self) -> None:
        lines = (
            _line("Prologue . . . . . . . . . . . .", block=0),
            _line("2", top=MIDDLE, block=1),
        )

        assert all(not d.kind.is_spoken for d in drafts_from_lines(lines))

    def test_a_bare_number_in_prose_is_left_alone(self) -> None:
        lines = (
            _line("The answer came to him.", block=0),
            _line("42", top=MIDDLE, block=1),
            _line("He wrote it down.", block=2),
        )
        drafts = drafts_from_lines(lines)

        assert all(d.kind is BlockKind.PARAGRAPH for d in drafts)


class TestDegenerateInput:
    def test_joining_skips_blank_parts(self) -> None:
        assert join_paragraph_lines(("First", "   ", "second.")) == "First second."

    def test_a_non_breaking_hyphen_also_heals_a_word_split_across_lines(self) -> None:
        # A typeset PDF breaks words on a non-breaking hyphen as readily as on
        # a plain one. Healing only the plain kind leaves "tra- jectories",
        # which then matches nothing in the dehyphenated source text.
        assert join_paragraph_lines(("These events form tra‑", "jectories.")) == (
            "These events form trajectories."
        )

    def test_a_non_breaking_hyphen_before_a_capital_is_left_alone(self) -> None:
        # An uppercase continuation is a real compound, not a split word.
        assert join_paragraph_lines(("Latency‑", "Aware Design")) == (
            "Latency‑ Aware Design"
        )

    def test_lines_reporting_no_font_size_yield_no_headings(self) -> None:
        # A malformed PDF can report a span size of zero, which would make
        # every short line compare as larger than the body text.
        lines = (
            _line("Short line", size=0.0, block=0),
            _line("Another short line", size=0.0, block=1),
        )

        assert all(d.kind is BlockKind.PARAGRAPH for d in drafts_from_lines(lines))
