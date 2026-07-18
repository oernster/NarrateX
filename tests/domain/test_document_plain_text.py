"""Tests for building the document model from plain text."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.plain_text import build_document, scan_blocks


def _kinds(source: str) -> list[BlockKind]:
    return [b.kind for b in scan_blocks(source=source)]


def _texts(source: str) -> list[str]:
    return [b.text for b in scan_blocks(source=source)]


class TestSpans:
    def test_empty_source_yields_no_blocks(self) -> None:
        assert scan_blocks(source="") == ()

    def test_none_source_yields_no_blocks(self) -> None:
        assert scan_blocks(source=None) == ()  # type: ignore[arg-type]

    def test_whitespace_only_source_yields_no_blocks(self) -> None:
        assert scan_blocks(source="   \n\n   \n") == ()

    def test_spans_are_exact_because_no_anchoring_is_needed(self) -> None:
        source = "CHAPTER ONE\n\nThe opening line of prose.\n"

        for block in scan_blocks(source=source):
            assert source[block.source_start : block.source_end].strip() == block.text

    def test_spans_are_ordered_and_non_overlapping(self) -> None:
        source = "CHAPTER ONE\n\nFirst para.\n\nSecond para.\n\n12\n"
        blocks = scan_blocks(source=source)

        for earlier, later in zip(blocks, blocks[1:]):
            assert earlier.source_end <= later.source_start


class TestHeadings:
    @pytest.mark.parametrize(
        "line",
        [
            "Chapter 4",
            "Chapter IV",
            "Part Two",
            "Book III",
            "Appendix A",
            "Section 2",
            "Volume 1",
        ],
    )
    def test_numbered_divisions_are_headings(self, line: str) -> None:
        blocks = scan_blocks(source=f"{line}\n\nSome prose follows here.\n")

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 1

    @pytest.mark.parametrize(
        "line",
        ["Prologue", "Epilogue", "Introduction", "Foreword", "Contents", "Index"],
    )
    def test_standalone_divisions_are_headings(self, line: str) -> None:
        blocks = scan_blocks(source=f"{line}\n\nSome prose follows here.\n")

        assert blocks[0].kind is BlockKind.HEADING

    def test_a_division_name_with_a_trailing_period_still_counts(self) -> None:
        blocks = scan_blocks(source="Prologue.\n\nSome prose.\n")

        assert blocks[0].kind is BlockKind.HEADING

    def test_capitalised_short_lines_are_headings(self) -> None:
        blocks = scan_blocks(source="THE LONG GOODBYE\n\nProse follows.\n")

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 1

    def test_an_isolated_short_line_without_punctuation_is_a_heading(self) -> None:
        blocks = scan_blocks(source="A Quiet Beginning\n\nProse follows here.\n")

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 2

    def test_a_short_line_ending_in_punctuation_is_prose(self) -> None:
        blocks = scan_blocks(source="He left.\n\nProse follows here.\n")

        assert blocks[0].kind is BlockKind.PARAGRAPH

    def test_a_long_line_is_never_a_heading(self) -> None:
        long_line = " ".join(["word"] * 30)
        blocks = scan_blocks(source=f"{long_line}\n\nMore prose.\n")

        assert blocks[0].kind is BlockKind.PARAGRAPH

    def test_a_short_line_inside_a_paragraph_is_not_a_heading(self) -> None:
        # Not isolated: it is the first line of a wrapped paragraph.
        source = "A Quiet Beginning\nis how the story starts, quietly.\n"
        blocks = scan_blocks(source=source)

        assert [b.kind for b in blocks] == [BlockKind.PARAGRAPH]

    def test_a_shouted_line_needs_letters(self) -> None:
        # "12" is equal to its own uppercase but is a page number, not a title.
        blocks = scan_blocks(source="12\n\nProse follows here.\n")

        assert blocks[0].kind is BlockKind.PAGE_NUMBER


class TestArtefacts:
    def test_a_standalone_number_is_a_page_number(self) -> None:
        blocks = scan_blocks(source="Prose here.\n\n12\n\nMore prose.\n")

        assert blocks[1].kind is BlockKind.PAGE_NUMBER

    def test_a_dotted_leader_line_is_a_contents_entry(self) -> None:
        source = "Prologue . . . . . . . . . . 2\n\nProse follows.\n"

        assert scan_blocks(source=source)[0].kind is BlockKind.TOC_ENTRY

    def test_a_rule_is_a_separator(self) -> None:
        blocks = scan_blocks(source="Prose here.\n\n---\n\nMore prose.\n")

        assert blocks[1].kind is BlockKind.SEPARATOR

    def test_a_frequently_repeated_short_line_is_a_running_head(self) -> None:
        source = "\n\n".join(["A History of Everything", "Some prose here."] * 4)
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is BlockKind.RUNNING_HEAD

    def test_two_repeats_are_not_enough(self) -> None:
        source = "\n\n".join(["A History of Everything", "Some prose here."] * 2)
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is not BlockKind.RUNNING_HEAD

    def test_repeated_prose_ending_in_punctuation_is_not_furniture(self) -> None:
        source = "\n\n".join(["Yes."] * 5)
        blocks = scan_blocks(source=source)

        assert all(b.kind is not BlockKind.RUNNING_HEAD for b in blocks)

    def test_no_artefact_is_spoken(self) -> None:
        source = "Prologue . . . . . . . . . . 2\n\n12\n\n---\n"

        for block in scan_blocks(source=source):
            assert block.is_spoken is False


class TestParagraphs:
    def test_hard_wrapped_lines_are_rejoined(self) -> None:
        source = "This sentence was\nwrapped over three\nseparate lines.\n"

        assert _texts(source) == [
            "This sentence was wrapped over three separate lines."
        ]

    def test_a_blank_line_separates_paragraphs(self) -> None:
        source = "First para.\n\nSecond para.\n"

        assert _texts(source) == ["First para.", "Second para."]

    def test_an_artefact_interrupts_a_paragraph(self) -> None:
        source = "Prose before.\n12\nProse after.\n"

        assert _kinds(source) == [
            BlockKind.PARAGRAPH,
            BlockKind.PAGE_NUMBER,
            BlockKind.PARAGRAPH,
        ]


class TestBuildDocument:
    SOURCE = (
        "CONTENTS\n"
        "\n"
        "Prologue . . . . . . . . . . 2\n"
        "\n"
        "Chapter 1\n"
        "\n"
        "It was a bright cold day\n"
        "and the clocks struck thirteen.\n"
        "\n"
        "12\n"
        "\n"
        "Chapter 2\n"
        "\n"
        "The second chapter begins.\n"
    )

    def test_source_length_matches_the_source(self) -> None:
        assert build_document(source=self.SOURCE).source_length == len(self.SOURCE)

    def test_sections_follow_the_headings(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert [s.title for s in doc.sections] == [
            "CONTENTS",
            "Chapter 1",
            "Chapter 2",
        ]

    def test_narration_skips_every_artefact(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert [b.text for b in doc.spoken_blocks] == [
            "CONTENTS",
            "Chapter 1",
            "It was a bright cold day and the clocks struck thirteen.",
            "Chapter 2",
            "The second chapter begins.",
        ]

    def test_contents_entries_and_folios_are_accounted_for_but_hidden(self) -> None:
        doc = build_document(source=self.SOURCE)
        kinds = {b.kind for b in doc.blocks}

        assert BlockKind.TOC_ENTRY in kinds
        assert BlockKind.PAGE_NUMBER in kinds
        assert doc.covered_ratio > doc.displayed_ratio

    def test_empty_source_yields_an_empty_document(self) -> None:
        doc = build_document(source="")

        assert doc.source_length == 0
        assert doc.sections == ()


class TestRunningHeadsDoNotEatContent:
    def test_chapter_titles_survive_repetition_detection(self) -> None:
        # The repetition key drops digits, so "Chapter 1", "Chapter 2" and
        # "Chapter 3" collide. A book's own chapter titles must not be
        # discarded as furniture because there are three or more of them.
        source = "\n\n".join(
            f"Chapter {n}\n\nSome prose for chapter {n} here." for n in range(1, 5)
        )
        blocks = scan_blocks(source=source)
        headings = [b for b in blocks if b.kind is BlockKind.HEADING]

        assert [h.text for h in headings] == [
            "Chapter 1",
            "Chapter 2",
            "Chapter 3",
            "Chapter 4",
        ]
        assert all(b.kind is not BlockKind.RUNNING_HEAD for b in blocks)

    def test_a_repeated_line_inside_a_paragraph_stays_prose(self) -> None:
        # Not isolated: it is the first line of a wrapped paragraph that
        # happens to recur. Treating it as furniture would delete real text.
        source = "\n\n".join(
            ["It was a bright cold day in April\nand the clocks struck thirteen."] * 5
        )
        blocks = scan_blocks(source=source)

        assert all(b.kind is BlockKind.PARAGRAPH for b in blocks)
        assert len(blocks) == 5

    def test_an_isolated_repeated_title_is_still_furniture(self) -> None:
        source = "\n\n".join(["THE LONG GOODBYE", "Some prose here."] * 4)
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is BlockKind.RUNNING_HEAD
