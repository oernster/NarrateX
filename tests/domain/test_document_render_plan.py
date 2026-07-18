"""Tests for the reading-pane render plan and its offset mapping."""

from __future__ import annotations

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Document, Section
from voice_reader.domain.document.plain_text import build_document
from voice_reader.domain.document.render_plan import build_render_plan


def _block(kind: BlockKind, start: int, end: int, text: str, level: int = 0) -> Block:
    return Block(
        kind=kind,
        source_start=start,
        source_end=end,
        text=text,
        level=level,
    )


def _document(*blocks: Block, length: int = 500) -> Document:
    section = Section(
        title="",
        source_start=blocks[0].source_start if blocks else 0,
        source_end=blocks[-1].source_end if blocks else 0,
        blocks=blocks,
    )
    return Document(source_length=length, sections=(section,) if blocks else ())


class TestLayout:
    def test_an_empty_document_renders_nothing(self) -> None:
        plan = build_render_plan(Document(source_length=0))

        assert plan.text == ""
        assert plan.blocks == ()

    def test_only_displayed_blocks_reach_the_pane(self) -> None:
        doc = _document(
            _block(BlockKind.HEADING, 0, 9, "Chapter 1", level=1),
            _block(BlockKind.TOC_ENTRY, 10, 30, "Prologue ..... 2"),
            _block(BlockKind.PAGE_NUMBER, 31, 33, "12"),
            _block(BlockKind.RUNNING_HEAD, 34, 44, "The Title"),
            _block(BlockKind.PARAGRAPH, 45, 70, "The prose begins here."),
        )
        plan = build_render_plan(doc)

        assert plan.text == "Chapter 1\nThe prose begins here."
        assert [b.kind for b in plan.blocks] == [
            BlockKind.HEADING,
            BlockKind.PARAGRAPH,
        ]

    def test_a_block_with_no_text_is_skipped(self) -> None:
        doc = _document(
            _block(BlockKind.PARAGRAPH, 0, 5, ""),
            _block(BlockKind.PARAGRAPH, 6, 20, "Real text."),
        )
        plan = build_render_plan(doc)

        assert plan.text == "Real text."
        assert len(plan.blocks) == 1

    def test_render_spans_index_the_rendered_text(self) -> None:
        doc = _document(
            _block(BlockKind.HEADING, 0, 9, "Chapter 1", level=1),
            _block(BlockKind.PARAGRAPH, 45, 70, "The prose begins here."),
        )
        plan = build_render_plan(doc)

        for block in plan.blocks:
            assert plan.text[block.render_start : block.render_end] == block.text

    def test_heading_level_survives_into_the_plan(self) -> None:
        doc = _document(_block(BlockKind.HEADING, 0, 9, "Chapter 1", level=3))
        plan = build_render_plan(doc)

        assert plan.blocks[0].level == 3

    def test_positions_match_how_a_text_document_counts_them(self) -> None:
        # One position per character, plus exactly one per block separator.
        doc = _document(
            _block(BlockKind.PARAGRAPH, 0, 5, "alpha"),
            _block(BlockKind.PARAGRAPH, 10, 14, "beta"),
            _block(BlockKind.PARAGRAPH, 20, 25, "gamma"),
        )
        plan = build_render_plan(doc)

        assert [b.render_start for b in plan.blocks] == [0, 6, 11]
        assert plan.text == "alpha\nbeta\ngamma"


class TestSourceToRender:
    def _plan(self):
        return build_render_plan(
            _document(
                _block(BlockKind.PARAGRAPH, 100, 105, "alpha"),
                _block(BlockKind.TOC_ENTRY, 110, 130, "Skipped ..... 4"),
                _block(BlockKind.PARAGRAPH, 200, 204, "beta"),
            )
        )

    def test_an_empty_plan_maps_to_zero(self) -> None:
        plan = build_render_plan(Document(source_length=0))

        assert plan.to_render(500) == 0

    def test_the_start_of_a_block_maps_to_its_render_start(self) -> None:
        plan = self._plan()

        assert plan.to_render(100) == 0
        assert plan.to_render(200) == 6

    def test_an_offset_inside_a_block_keeps_its_position(self) -> None:
        plan = self._plan()

        assert plan.to_render(102) == 2

    def test_an_offset_before_everything_maps_to_the_first_block(self) -> None:
        plan = self._plan()

        assert plan.to_render(0) == 0

    def test_an_offset_inside_skipped_content_moves_to_the_next_visible_block(
        self,
    ) -> None:
        # 110-130 is a contents entry that the pane never shows, so the reader
        # should be taken to the next thing they can actually see.
        plan = self._plan()

        assert plan.to_render(120) == 6

    def test_an_offset_past_everything_clamps_to_the_end(self) -> None:
        plan = self._plan()

        assert plan.to_render(9999) == plan.blocks[-1].render_end


class TestRenderToSource:
    def _plan(self):
        return build_render_plan(
            _document(
                _block(BlockKind.PARAGRAPH, 100, 105, "alpha"),
                _block(BlockKind.PARAGRAPH, 200, 204, "beta"),
            )
        )

    def test_an_empty_plan_maps_to_zero(self) -> None:
        plan = build_render_plan(Document(source_length=0))

        assert plan.to_source(10) == 0

    def test_the_start_of_a_block_maps_to_its_source_start(self) -> None:
        plan = self._plan()

        assert plan.to_source(0) == 100
        assert plan.to_source(6) == 200

    def test_an_offset_inside_a_block_keeps_its_position(self) -> None:
        plan = self._plan()

        assert plan.to_source(2) == 102

    def test_a_click_on_a_separator_lands_on_the_next_block(self) -> None:
        # Position 5 is the newline between the two blocks.
        plan = self._plan()

        assert plan.to_source(5) == 200

    def test_an_offset_past_everything_clamps_to_the_end(self) -> None:
        plan = self._plan()

        assert plan.to_source(9999) == plan.blocks[-1].source_end


class TestRoundTrip:
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

    def test_the_pane_shows_no_artefacts(self) -> None:
        plan = build_render_plan(build_document(source=self.SOURCE))

        assert ". . . ." not in plan.text
        assert "\n12\n" not in plan.text

    def test_every_block_start_round_trips(self) -> None:
        plan = build_render_plan(build_document(source=self.SOURCE))

        for block in plan.blocks:
            assert plan.to_source(block.render_start) == block.source_start
            assert plan.to_render(block.source_start) == block.render_start

    def test_offsets_inside_blocks_round_trip(self) -> None:
        plan = build_render_plan(build_document(source=self.SOURCE))

        for block in plan.blocks:
            for step in range(0, block.render_end - block.render_start):
                render = block.render_start + step
                assert plan.to_render(plan.to_source(render)) == render

    def test_the_rendered_text_is_shorter_than_the_book(self) -> None:
        document = build_document(source=self.SOURCE)
        plan = build_render_plan(document)

        assert len(plan.text) < document.source_length


class TestBodyStart:
    SOURCE = (
        "CONTENTS\n"
        "\n"
        "Prologue . . . . . . . . . . 2\n"
        "\n"
        "Chapter 1\n"
        "\n"
        "The real chapter text begins here.\n"
    )

    def test_by_default_nothing_is_excluded_by_position(self) -> None:
        doc = build_document(source=self.SOURCE)
        plan = build_render_plan(doc)

        assert "CONTENTS" in plan.text

    def test_blocks_before_the_body_start_are_dropped(self) -> None:
        # A contents page's own titles are classified as headings, because that
        # is what they look like. Only position can exclude them.
        doc = build_document(source=self.SOURCE)
        body_start = self.SOURCE.index("Chapter 1\n\nThe real")
        plan = build_render_plan(doc, body_start=body_start)

        assert "CONTENTS" not in plan.text
        assert plan.text.startswith("Chapter 1")

    def test_offsets_stay_correct_after_excluding_front_matter(self) -> None:
        doc = build_document(source=self.SOURCE)
        body_start = self.SOURCE.index("Chapter 1\n\nThe real")
        plan = build_render_plan(doc, body_start=body_start)

        for block in plan.blocks:
            assert plan.to_source(block.render_start) == block.source_start
            assert plan.to_render(block.source_start) == block.render_start

    def test_a_body_start_past_everything_renders_nothing(self) -> None:
        doc = build_document(source=self.SOURCE)
        plan = build_render_plan(doc, body_start=len(self.SOURCE) + 1)

        assert plan.text == ""
        assert plan.blocks == ()


class TestOffsetsOutsideTheDocument:
    def test_a_negative_render_offset_maps_to_the_first_block(self) -> None:
        plan = build_render_plan(
            _document(_block(BlockKind.PARAGRAPH, 100, 105, "alpha"))
        )

        assert plan.to_source(-5) == 100

    def test_a_negative_source_offset_maps_to_the_first_block(self) -> None:
        plan = build_render_plan(
            _document(_block(BlockKind.PARAGRAPH, 100, 105, "alpha"))
        )

        assert plan.to_render(-5) == 0
