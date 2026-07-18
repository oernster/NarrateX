"""Render a document's plan into a text document with real typography.

The pane stops being a dump of the book's text and becomes a rendering of its
structure: headings sized by level, paragraphs spaced, lists indented, quotes
set apart, code in a monospace face.

Positions are not disturbed. The plan's text is set verbatim and formatting is
applied over it, so a render offset stays a valid cursor position and the
mapping back to the book's own offsets keeps working.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QTextBlockFormat, QTextCharFormat, QTextCursor

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.render_plan import RenderedBlock, RenderPlan
from voice_reader.ui._utf16_positions import Utf16PositionMap

# Point-size multipliers by heading level, largest first. Six entries to match
# the six levels the model expresses.
_HEADING_SCALE_BY_LEVEL = (1.90, 1.58, 1.36, 1.20, 1.10, 1.02)

# Space above and below a block, in points.
_HEADING_SPACE_ABOVE = 14.0
_HEADING_SPACE_BELOW = 6.0
_PARAGRAPH_SPACE_BELOW = 10.0
_QUOTE_SPACE = 8.0

# Left indent in points, applied per nesting level for lists.
_LIST_INDENT_PER_LEVEL = 18.0
_QUOTE_INDENT = 24.0

# Weight applied to headings.
_HEADING_WEIGHT = QFont.Weight.DemiBold

_MONOSPACE_FAMILIES = ("Consolas", "Menlo", "DejaVu Sans Mono", "monospace")


def heading_point_size(*, level: int, base: float) -> float:
    """Point size for a heading of `level`, relative to the body size.

    Levels outside the expressed range clamp to the nearest end rather than
    failing, because extraction can report a deeper level than six.
    """

    if level < 1:
        return base * _HEADING_SCALE_BY_LEVEL[0]
    index = min(level, len(_HEADING_SCALE_BY_LEVEL)) - 1
    return base * _HEADING_SCALE_BY_LEVEL[index]


def left_indent(*, kind: BlockKind, level: int) -> float:
    """Left indent in points for a block."""

    if kind is BlockKind.LIST_ITEM:
        return max(1, level) * _LIST_INDENT_PER_LEVEL
    if kind is BlockKind.BLOCK_QUOTE:
        return _QUOTE_INDENT
    return 0.0


def char_format_for(*, block: RenderedBlock, base: float) -> QTextCharFormat:
    """Character formatting for one block."""

    fmt = QTextCharFormat()

    if block.kind is BlockKind.HEADING:
        fmt.setFontPointSize(heading_point_size(level=block.level, base=base))
        fmt.setFontWeight(_HEADING_WEIGHT)
        return fmt

    fmt.setFontPointSize(base)

    if block.kind is BlockKind.BLOCK_QUOTE:
        fmt.setFontItalic(True)
    elif block.kind is BlockKind.CODE:
        fmt.setFontFamilies(list(_MONOSPACE_FAMILIES))

    return fmt


def block_format_for(*, block: RenderedBlock) -> QTextBlockFormat:
    """Paragraph formatting for one block."""

    fmt = QTextBlockFormat()
    fmt.setLeftMargin(left_indent(kind=block.kind, level=block.level))

    if block.kind is BlockKind.HEADING:
        fmt.setTopMargin(_HEADING_SPACE_ABOVE)
        fmt.setBottomMargin(_HEADING_SPACE_BELOW)
        return fmt

    if block.kind is BlockKind.BLOCK_QUOTE:
        fmt.setTopMargin(_QUOTE_SPACE)
        fmt.setBottomMargin(_QUOTE_SPACE)
        return fmt

    fmt.setBottomMargin(_PARAGRAPH_SPACE_BELOW)
    return fmt


def apply_render_plan(
    *,
    text_edit,
    plan: RenderPlan,
    base_point_size: float,
) -> Utf16PositionMap:
    """Fill `text_edit` from `plan`, formatting each block by its kind.

    Returns the position map for the text that was set. Callers need it: a
    render offset is a Python index, while a cursor position counts UTF-16
    units, and the two diverge as soon as the book contains an emoji.
    """

    positions = Utf16PositionMap.for_text(plan.text)

    document = text_edit.document()
    document.setUndoRedoEnabled(False)
    try:
        text_edit.setPlainText(plan.text)

        cursor = QTextCursor(document)
        for block in plan.blocks:
            cursor.setPosition(positions.to_qt(block.render_start))
            cursor.setPosition(
                positions.to_qt(block.render_end),
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.mergeCharFormat(char_format_for(block=block, base=base_point_size))
            cursor.mergeBlockFormat(block_format_for(block=block))

        # Leave the caret at the start rather than inside the last block.
        reset = QTextCursor(document)
        reset.setPosition(0)
        text_edit.setTextCursor(reset)
    finally:
        document.setUndoRedoEnabled(True)

    return positions
