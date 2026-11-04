"""Tests for typesetting script markers in a real text document."""

from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.render_plan import RenderedBlock, RenderPlan
from voice_reader.domain.document.script_markup import ScriptKind
from voice_reader.ui.document_renderer import apply_render_plan
from voice_reader.ui.script_typesetting import (
    HIDDEN_POINT_SIZE,
    SCRIPT_SCALE,
    SUBSCRIPT_DROP_PERCENT,
    SUPERSCRIPT_RISE_PERCENT,
    script_format,
    typeset_plain_text,
)
from tests.ui._dispose_testkit import dispose

BASE = 10.0


def _format_at(edit: QTextEdit, index: int):
    cursor = QTextCursor(edit.document())
    cursor.setPosition(index + 1)
    return cursor.charFormat()


def test_a_marker_is_hidden_and_takes_next_to_no_width(qapp) -> None:
    del qapp
    fmt = script_format(kind=ScriptKind.MARKER, shifts=(), base_point_size=BASE)

    assert fmt.fontPointSize() == HIDDEN_POINT_SIZE
    assert fmt.foreground().color().alpha() == 0


def test_nested_scripts_shrink_and_shift_level_by_level(qapp) -> None:
    del qapp
    shifts = (ScriptKind.SUPERSCRIPT, ScriptKind.SUBSCRIPT)
    fmt = script_format(kind=ScriptKind.SUBSCRIPT, shifts=shifts, base_point_size=BASE)

    assert fmt.fontPointSize() == BASE * SCRIPT_SCALE**2
    assert fmt.baselineOffset() == SUPERSCRIPT_RISE_PERCENT - SUBSCRIPT_DROP_PERCENT


def test_raw_text_has_its_scripts_typeset(qapp) -> None:
    del qapp
    edit = QTextEdit()
    edit.setPlainText("H_{2}O")

    assert typeset_plain_text(edit) == 3
    assert _format_at(edit, 2).foreground().color().alpha() == 0
    assert _format_at(edit, 3).baselineOffset() == -SUBSCRIPT_DROP_PERCENT
    assert edit.toPlainText() == "H_{2}O"
    dispose(edit)


def _block(kind: BlockKind, start: int, text: str) -> RenderedBlock:
    return RenderedBlock(
        kind=kind,
        level=0,
        text=text,
        render_start=start,
        render_end=start + len(text),
        source_start=start,
        source_end=start + len(text),
    )


def test_a_plan_typesets_prose_but_leaves_code_as_typed(qapp) -> None:
    del qapp
    prose, code = "O_{2}", "x_{2}"
    text = f"{prose}\n{code}"
    blocks = (
        _block(BlockKind.PARAGRAPH, 0, prose),
        _block(BlockKind.CODE, len(prose) + 1, code),
    )
    plan = RenderPlan(
        text=text,
        blocks=blocks,
        render_starts=tuple(b.render_start for b in blocks),
        source_starts=tuple(b.source_start for b in blocks),
    )
    edit = QTextEdit()

    apply_render_plan(text_edit=edit, plan=plan, base_point_size=BASE)

    assert _format_at(edit, 3).baselineOffset() == -SUBSCRIPT_DROP_PERCENT
    assert _format_at(edit, len(prose) + 1 + 3).baselineOffset() == 0
    dispose(edit)
