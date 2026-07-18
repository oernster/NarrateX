"""Tests for rendering a document plan with typography."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.model import Block, Document, Section
from voice_reader.domain.document.render_plan import RenderedBlock, build_render_plan
from voice_reader.ui.document_renderer import (
    apply_render_plan,
    block_format_for,
    char_format_for,
    heading_point_size,
    left_indent,
)

BASE = 12.0


def _rendered(kind: BlockKind, level: int = 0, text: str = "x") -> RenderedBlock:
    return RenderedBlock(
        kind=kind,
        level=level,
        text=text,
        render_start=0,
        render_end=len(text),
        source_start=0,
        source_end=len(text),
    )


class TestHeadingPointSize:
    def test_a_top_level_heading_is_the_largest(self) -> None:
        sizes = [heading_point_size(level=level, base=BASE) for level in range(1, 7)]

        assert sizes == sorted(sizes, reverse=True)

    def test_every_heading_is_at_least_body_size(self) -> None:
        for level in range(1, 7):
            assert heading_point_size(level=level, base=BASE) >= BASE

    def test_a_level_below_one_clamps_to_the_largest(self) -> None:
        assert heading_point_size(level=0, base=BASE) == heading_point_size(
            level=1, base=BASE
        )

    def test_a_level_beyond_the_range_clamps_to_the_smallest(self) -> None:
        # Extraction can report a deeper level than the model expresses.
        assert heading_point_size(level=99, base=BASE) == heading_point_size(
            level=6, base=BASE
        )

    def test_size_scales_with_the_body_size(self) -> None:
        small = heading_point_size(level=1, base=10.0)
        large = heading_point_size(level=1, base=20.0)

        assert large == pytest.approx(small * 2.0)


class TestIndent:
    def test_prose_is_not_indented(self) -> None:
        assert left_indent(kind=BlockKind.PARAGRAPH, level=0) == 0.0

    def test_a_heading_is_not_indented(self) -> None:
        assert left_indent(kind=BlockKind.HEADING, level=1) == 0.0

    def test_a_quote_is_indented(self) -> None:
        assert left_indent(kind=BlockKind.BLOCK_QUOTE, level=0) > 0.0

    def test_list_indent_grows_with_nesting(self) -> None:
        first = left_indent(kind=BlockKind.LIST_ITEM, level=1)
        second = left_indent(kind=BlockKind.LIST_ITEM, level=2)

        assert second > first > 0.0

    def test_a_list_item_with_no_level_still_indents(self) -> None:
        assert left_indent(kind=BlockKind.LIST_ITEM, level=0) > 0.0


class TestCharFormat:
    def test_a_heading_is_larger_and_heavier_than_prose(self, qapp) -> None:
        heading = char_format_for(block=_rendered(BlockKind.HEADING, 1), base=BASE)
        prose = char_format_for(block=_rendered(BlockKind.PARAGRAPH), base=BASE)

        assert heading.fontPointSize() > prose.fontPointSize()
        assert heading.fontWeight() > prose.fontWeight()

    def test_prose_is_set_at_the_body_size(self, qapp) -> None:
        fmt = char_format_for(block=_rendered(BlockKind.PARAGRAPH), base=BASE)

        assert fmt.fontPointSize() == pytest.approx(BASE)

    def test_a_quote_is_italic(self, qapp) -> None:
        fmt = char_format_for(block=_rendered(BlockKind.BLOCK_QUOTE), base=BASE)

        assert fmt.fontItalic() is True

    def test_code_is_monospace(self, qapp) -> None:
        fmt = char_format_for(block=_rendered(BlockKind.CODE), base=BASE)

        assert fmt.fontFamilies()

    def test_prose_is_neither_italic_nor_monospace(self, qapp) -> None:
        fmt = char_format_for(block=_rendered(BlockKind.PARAGRAPH), base=BASE)

        assert fmt.fontItalic() is False
        assert not fmt.fontFamilies()


class TestBlockFormat:
    def test_a_heading_has_space_above_it(self, qapp) -> None:
        fmt = block_format_for(block=_rendered(BlockKind.HEADING, 1))

        assert fmt.topMargin() > 0.0

    def test_a_paragraph_has_space_below_it(self, qapp) -> None:
        fmt = block_format_for(block=_rendered(BlockKind.PARAGRAPH))

        assert fmt.bottomMargin() > 0.0

    def test_a_quote_is_set_apart_above_and_below(self, qapp) -> None:
        fmt = block_format_for(block=_rendered(BlockKind.BLOCK_QUOTE))

        assert fmt.topMargin() > 0.0
        assert fmt.bottomMargin() > 0.0
        assert fmt.leftMargin() > 0.0

    def test_a_list_item_is_indented(self, qapp) -> None:
        fmt = block_format_for(block=_rendered(BlockKind.LIST_ITEM, level=2))

        assert fmt.leftMargin() > 0.0


class TestApplyRenderPlan:
    def _plan(self):
        blocks = (
            Block(
                kind=BlockKind.HEADING,
                source_start=0,
                source_end=9,
                text="Chapter 1",
                level=1,
            ),
            Block(
                kind=BlockKind.PARAGRAPH,
                source_start=20,
                source_end=40,
                text="The prose begins.",
            ),
            Block(
                kind=BlockKind.TOC_ENTRY,
                source_start=50,
                source_end=70,
                text="Skipped ..... 4",
            ),
        )
        section = Section(
            title="Chapter 1", source_start=0, source_end=70, blocks=blocks
        )
        return build_render_plan(Document(source_length=100, sections=(section,)))

    def _edit(self, qapp):
        from voice_reader.ui.seekable_text_edit import SeekableTextEdit

        return SeekableTextEdit()

    def test_the_pane_shows_the_planned_text(self, qapp) -> None:
        edit = self._edit(qapp)
        plan = self._plan()

        apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)

        assert edit.toPlainText() == plan.text

    def test_artefacts_never_reach_the_pane(self, qapp) -> None:
        edit = self._edit(qapp)

        apply_render_plan(text_edit=edit, plan=self._plan(), base_point_size=BASE)

        assert "Skipped" not in edit.toPlainText()

    def test_cursor_positions_still_match_render_offsets(self, qapp) -> None:
        # The whole mapping rests on this: a render offset must remain a valid
        # cursor position after formatting is applied.
        from PySide6.QtGui import QTextCursor

        edit = self._edit(qapp)
        plan = self._plan()
        apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)

        for block in plan.blocks:
            cursor = QTextCursor(edit.document())
            cursor.setPosition(block.render_start)
            cursor.setPosition(block.render_end, QTextCursor.MoveMode.KeepAnchor)
            assert cursor.selectedText() == block.text

    def test_the_heading_is_rendered_larger_than_the_prose(self, qapp) -> None:
        from PySide6.QtGui import QTextCursor

        edit = self._edit(qapp)
        plan = self._plan()
        apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)

        def size_at(position: int) -> float:
            cursor = QTextCursor(edit.document())
            cursor.setPosition(position + 1)
            return cursor.charFormat().fontPointSize()

        assert size_at(plan.blocks[0].render_start) > size_at(
            plan.blocks[1].render_start
        )

    def test_the_caret_starts_at_the_top(self, qapp) -> None:
        edit = self._edit(qapp)

        apply_render_plan(text_edit=edit, plan=self._plan(), base_point_size=BASE)

        assert edit.textCursor().position() == 0

    def test_undo_history_is_restored_afterwards(self, qapp) -> None:
        edit = self._edit(qapp)

        apply_render_plan(text_edit=edit, plan=self._plan(), base_point_size=BASE)

        assert edit.document().isUndoRedoEnabled() is True

    def test_rendering_an_empty_plan_clears_the_pane(self, qapp) -> None:
        edit = self._edit(qapp)
        empty = build_render_plan(Document(source_length=0))

        apply_render_plan(text_edit=edit, plan=empty, base_point_size=BASE)

        assert edit.toPlainText() == ""

    def test_rendering_twice_replaces_rather_than_appends(self, qapp) -> None:
        edit = self._edit(qapp)
        plan = self._plan()

        apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)
        apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)

        assert edit.toPlainText() == plan.text
