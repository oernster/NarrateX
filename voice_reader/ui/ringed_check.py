"""A checkbox whose ring goes round the box rather than round the words.

Ported from Stellody, whose notes are the measurement behind it and are worth
keeping: Qt draws a checkbox's square itself, so the moment a stylesheet names
`::indicator` it takes the whole subcontrol over. A rule setting only a border
there leaves an empty square with no tick in it, while a rule scoped to
`:focus` alone changes nothing at all. Owning the square in the sheet therefore
means inventing a checked picture and an unchecked one, which is a redrawn
checkbox rather than a ring on the one Qt already draws.

So the ring is painted over the square Qt has drawn, at the rectangle Qt itself
reports for it. The room comes from the padding the stylesheet gives the
control.

The colours arrive through the stylesheet as properties rather than from a mode
handed down by the window, so the palette stays the one home for both values.
They are properties rather than states because a `qproperty` is read when the
widget is polished; which of the two to paint is then the widget's own
question, asked of its own state. The three states are the ones every other
control here wears: nothing at rest, the ring under focus or the pointer, the
danger colour while it cannot be pressed.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton, QWidget

RING_PX = 2
RING_RADIUS_PX = 4
# Drawn outside the square rather than on its edge, so it reads as a ring round
# the box instead of as a recolouring of the box's own border.
RING_INSET_PX = -2


class RingedCheckBox(QCheckBox):
    """A checkbox that paints its own ring, on the square and nowhere else."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        # Without this Qt sends no hover events to a widget that is not
        # stylesheet-painted, so the ring would answer focus but not the mouse.
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._ring = ""
        self._danger = ""

    def _read_ring(self) -> str:
        """The colour a focused or hovered box is ringed in."""

        return self._ring

    def _write_ring(self, colour: str) -> None:
        """Take the colour the stylesheet is handing down."""

        self._ring = colour
        self.update()

    def _read_danger(self) -> str:
        """The colour a box that cannot be pressed is ringed in."""

        return self._danger

    def _write_danger(self, colour: str) -> None:
        """Take the colour the stylesheet is handing down."""

        self._danger = colour
        self.update()

    ringColour = Property(str, _read_ring, _write_ring)
    dangerColour = Property(str, _read_danger, _write_danger)

    def ring_now(self) -> str:
        """Which state this box is in; empty for no ring at all."""

        if not self.isEnabled():
            return self._danger
        if self.hasFocus() or self.underMouse():
            return self._ring
        return ""

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Qt's own checkbox, then the ring over the square it drew."""

        super().paintEvent(event)
        colour = self.ring_now()
        if not colour:
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        square = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, option, self
        )
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(colour), RING_PX))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                square.adjusted(
                    RING_INSET_PX, RING_INSET_PX, -RING_INSET_PX, -RING_INSET_PX
                ),
                RING_RADIUS_PX,
                RING_RADIUS_PX,
            )
        finally:
            painter.end()
