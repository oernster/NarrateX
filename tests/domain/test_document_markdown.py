"""Tests for building the document model from markdown source."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.markdown import build_document, scan_blocks


def _kinds(source: str) -> list[BlockKind]:
    return [b.kind for b in scan_blocks(source=source)]


def _texts(source: str) -> list[str]:
    return [b.text for b in scan_blocks(source=source)]


class TestSpans:
    def test_every_block_span_indexes_the_source(self) -> None:
        source = (
            "# Title\n"
            "\n"
            "First paragraph here.\n"
            "\n"
            "- item one\n"
            "- item two\n"
            "\n"
            "> a quotation\n"
        )
        for block in scan_blocks(source=source):
            assert 0 <= block.source_start <= block.source_end <= len(source)

    def test_a_heading_span_covers_its_source_line(self) -> None:
        source = "# Title\n\nbody"
        heading = scan_blocks(source=source)[0]

        assert source[heading.source_start : heading.source_end] == "# Title"

    def test_spans_are_non_overlapping_and_in_reading_order(self) -> None:
        source = "# One\n\npara one\n\n## Two\n\npara two\n"
        blocks = scan_blocks(source=source)

        for earlier, later in zip(blocks, blocks[1:]):
            assert earlier.source_end <= later.source_start


class TestHeadings:
    def test_atx_headings_carry_their_level(self) -> None:
        source = "# One\n\n## Two\n\n### Three\n"
        blocks = scan_blocks(source=source)

        assert [(b.text, b.level) for b in blocks] == [
            ("One", 1),
            ("Two", 2),
            ("Three", 3),
        ]

    def test_setext_underline_after_prose_is_a_heading(self) -> None:
        source = "The Title\n===\n\nbody text\n"
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 1
        assert blocks[0].text == "The Title"

    def test_setext_dash_underline_is_level_two(self) -> None:
        blocks = scan_blocks(source="The Title\n---\n")

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 2

    def test_a_setext_heading_span_covers_prose_and_underline(self) -> None:
        source = "The Title\n---\n"
        heading = scan_blocks(source=source)[0]

        assert source[heading.source_start : heading.source_end] == "The Title\n---"

    def test_a_rule_with_no_preceding_prose_is_a_separator(self) -> None:
        assert _kinds("---\n") == [BlockKind.SEPARATOR]

    def test_a_rule_after_a_blank_line_is_a_separator(self) -> None:
        assert _kinds("body\n\n---\n") == [
            BlockKind.PARAGRAPH,
            BlockKind.SEPARATOR,
        ]

    def test_heading_text_has_inline_syntax_stripped(self) -> None:
        assert _texts("# A **bold** title\n") == ["A bold title"]


class TestParagraphs:
    def test_hard_wrapped_lines_are_rejoined(self) -> None:
        source = "This sentence was\nhard wrapped across\nthree lines.\n"

        assert _texts(source) == ["This sentence was hard wrapped across three lines."]

    def test_a_blank_line_separates_paragraphs(self) -> None:
        source = "First para.\n\nSecond para.\n"

        assert _texts(source) == ["First para.", "Second para."]

    def test_inline_syntax_is_stripped(self) -> None:
        assert _texts("A *very* [linked](url) line.\n") == ["A very linked line."]

    def test_a_paragraph_that_strips_to_nothing_is_dropped(self) -> None:
        assert scan_blocks(source="[]()\n") == ()

    def test_empty_source_yields_no_blocks(self) -> None:
        assert scan_blocks(source="") == ()


class TestListsAndQuotes:
    def test_each_list_item_is_its_own_block(self) -> None:
        source = "- one\n- two\n- three\n"
        blocks = scan_blocks(source=source)

        assert [b.kind for b in blocks] == [BlockKind.LIST_ITEM] * 3
        assert [b.text for b in blocks] == ["one", "two", "three"]

    def test_nested_items_carry_a_deeper_level(self) -> None:
        source = "- outer\n  - inner\n"
        blocks = scan_blocks(source=source)

        assert [b.level for b in blocks] == [1, 2]

    def test_consecutive_quote_lines_form_one_block(self) -> None:
        source = "> first line\n> second line\n\nbody\n"
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is BlockKind.BLOCK_QUOTE
        assert blocks[0].text == "first line second line"
        assert blocks[1].kind is BlockKind.PARAGRAPH

    def test_a_blank_quote_line_does_not_add_empty_text(self) -> None:
        blocks = scan_blocks(source="> first\n>\n> second\n")

        assert blocks[0].text == "first second"


class TestFencedCode:
    def test_code_is_captured_without_the_fences(self) -> None:
        source = "```python\nx = 1\ny = 2\n```\n"
        blocks = scan_blocks(source=source)

        assert blocks[0].kind is BlockKind.CODE
        assert blocks[0].text == "x = 1\ny = 2"

    def test_markdown_inside_code_is_not_interpreted(self) -> None:
        source = "```\n# not a heading\n- not a list\n```\n"
        blocks = scan_blocks(source=source)

        assert [b.kind for b in blocks] == [BlockKind.CODE]

    def test_an_unterminated_fence_still_yields_a_block(self) -> None:
        blocks = scan_blocks(source="```\nx = 1\n")

        assert [b.kind for b in blocks] == [BlockKind.CODE]
        assert blocks[0].text == "x = 1"

    def test_a_mismatched_fence_does_not_close_the_block(self) -> None:
        source = "```\nx = 1\n~~~\ny = 2\n```\n"
        blocks = scan_blocks(source=source)

        assert [b.kind for b in blocks] == [BlockKind.CODE]
        assert blocks[0].text == "x = 1\n~~~\ny = 2"

    def test_code_is_displayed_but_not_spoken(self) -> None:
        block = scan_blocks(source="```\nx = 1\n```\n")[0]

        assert block.is_displayed is True
        assert block.is_spoken is False


class TestBuildDocument:
    SOURCE = (
        "Front matter line.\n"
        "\n"
        "# Chapter One\n"
        "\n"
        "The opening paragraph\n"
        "wrapped over two lines.\n"
        "\n"
        "## Section A\n"
        "\n"
        "- first point\n"
        "- second point\n"
        "\n"
        "# Chapter Two\n"
        "\n"
        "Closing prose.\n"
    )

    def test_source_length_matches_the_source(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert doc.source_length == len(self.SOURCE)

    def test_sections_follow_the_headings(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert [s.title for s in doc.sections] == [
            "",
            "Chapter One",
            "Section A",
            "Chapter Two",
        ]

    def test_contents_skip_the_untitled_front_matter(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert [(e.title, e.level) for e in doc.toc] == [
            ("Chapter One", 1),
            ("Section A", 2),
            ("Chapter Two", 1),
        ]

    def test_every_contents_entry_resolves_into_the_source(self) -> None:
        doc = build_document(source=self.SOURCE)

        for entry in doc.toc:
            assert entry.is_resolved
            assert 0 <= int(entry.target_source_offset or 0) < len(self.SOURCE)

    def test_body_starts_at_the_first_spoken_block(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert doc.body_start_offset == 0

    def test_narration_order_reads_headings_then_prose(self) -> None:
        doc = build_document(source=self.SOURCE)

        assert [b.text for b in doc.spoken_blocks] == [
            "Front matter line.",
            "Chapter One",
            "The opening paragraph wrapped over two lines.",
            "Section A",
            "first point",
            "second point",
            "Chapter Two",
            "Closing prose.",
        ]

    def test_most_of_the_source_is_accounted_for(self) -> None:
        doc = build_document(source=self.SOURCE)

        # Only blank lines and the heading markers themselves fall outside a
        # displayed block, so coverage should be high.
        assert doc.structured_ratio > 0.75

    def test_empty_source_yields_an_empty_document(self) -> None:
        doc = build_document(source="")

        assert doc.source_length == 0
        assert doc.sections == ()
        assert doc.toc == ()

    def test_none_source_is_treated_as_empty(self) -> None:
        doc = build_document(source=None)  # type: ignore[arg-type]

        assert doc.source_length == 0
