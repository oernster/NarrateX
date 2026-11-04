"""Typeset the subscripts and superscripts a formula's plain notation marks.

The book's text writes "O_{2}" so the narrator can say "O sub 2". The pane
shows O with a lowered 2: each marker is kept in the document, so every
position, highlight and click offset stays exactly what it was; the marker is set
invisible and next to no width; the content is set smaller and moved off the
baseline, nesting as deep as the formula does. Measured on 2026-11-04 in the
reading pane's face: "H_{2}O" reads as H₂O, beside a plain "O2" for width.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

from voice_reader.domain.document.script_markup import ScriptKind, script_runs
from voice_reader.ui._utf16_positions import Utf16PositionMap

# Each level of script is set at this fraction of the level outside it.
SCRIPT_SCALE = 0.7

# How far a script moves off the baseline, as a percentage of the line's font
# height: up for a superscript, down for a subscript.
SUPERSCRIPT_RISE_PERCENT = 33.0
SUBSCRIPT_DROP_PERCENT = 20.0

# A marker stays in the document but is drawn at a size that takes next to no
# width, in a colour that draws nothing.
HIDDEN_POINT_SIZE = 0.1
_INVISIBLE = QColor(0, 0, 0, 0)


def script_format(*, kind: ScriptKind, shifts, base_point_size: float):
    """The character format for one run: a hidden marker or script content."""

    fmt = QTextCharFormat()
    if kind is ScriptKind.MARKER:
        fmt.setFontPointSize(HIDDEN_POINT_SIZE)
        fmt.setForeground(_INVISIBLE)
        return fmt
    offset = 0.0
    for shift in shifts:
        if shift is ScriptKind.SUPERSCRIPT:
            offset += SUPERSCRIPT_RISE_PERCENT
        else:
            offset -= SUBSCRIPT_DROP_PERCENT
    fmt.setFontPointSize(base_point_size * SCRIPT_SCALE ** len(shifts))
    fmt.setBaselineOffset(offset)
    return fmt


def typeset_scripts(
    *,
    cursor: QTextCursor,
    positions: Utf16PositionMap,
    text: str,
    start: int,
    end: int,
    base_point_size: float,
) -> int:
    """Typeset every script between `start` and `end`; the count of runs set.

    Runs are applied in the order found, which puts an inner script after the
    outer one holding it, so each character ends with its innermost format.
    """

    runs = script_runs(text, start, end)
    for run in runs:
        cursor.setPosition(positions.to_qt(run.start))
        cursor.setPosition(positions.to_qt(run.end), QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(
            script_format(
                kind=run.kind, shifts=run.shifts, base_point_size=base_point_size
            )
        )
    return len(runs)


def typeset_plain_text(text_edit) -> int:
    """Typeset the scripts of a pane that shows raw text with no structure."""

    text = text_edit.toPlainText()
    cursor = QTextCursor(text_edit.document())
    cursor.beginEditBlock()
    try:
        return typeset_scripts(
            cursor=cursor,
            positions=Utf16PositionMap.for_text(text),
            text=text,
            start=0,
            end=len(text),
            base_point_size=text_edit.font().pointSizeF(),
        )
    finally:
        cursor.endEditBlock()
