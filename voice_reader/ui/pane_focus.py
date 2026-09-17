"""A reading pane is a keyboard stop only while it has somewhere to scroll.

A pane is chrome, not a control: it holds content rather than being something
to act on. Qt gives the whole scroll area family StrongFocus by default, so a
click anywhere in a licence, the Guide or the reader focused the pane and drew
a ring round it. The ring said nothing that could be acted on.

Two changes, as in Stellody's ReadingPane; the first is what a reader notices:

TabFocus rather than StrongFocus, so a CLICK never focuses it. The ring then
only ever appears because somebody tabbed there, which is the one time it
means anything.

Then the stop itself is conditional. A page that fits its viewport scrolls
nowhere, so it drops off the ring entirely; a page that overflows keeps the
stop, because a long text with no controls of its own could not be read from
the keyboard otherwise. It is re-decided every time either scrollbar's range
changes (content loaded, dialog resized). The viewport is a separate focusable
child and is never a stop.

A dialog must not OPEN on a reading pane either; see first_stop_dialog.py.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt


class OverflowFocus(QObject):
    def __init__(self, area) -> None:
        super().__init__(area)
        self._area = area
        area.viewport().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for bar in (area.verticalScrollBar(), area.horizontalScrollBar()):
            bar.rangeChanged.connect(lambda _low, _high: self.sync())
        self.sync()

    def overflows(self) -> bool:
        return (
            self._area.verticalScrollBar().maximum() > 0
            or self._area.horizontalScrollBar().maximum() > 0
        )

    def sync(self) -> None:
        self._area.setFocusPolicy(
            Qt.FocusPolicy.TabFocus if self.overflows() else Qt.FocusPolicy.NoFocus
        )


def as_pane(widget):
    """Mark `widget` as chrome: it holds controls and is never a keyboard stop.

    A plain QWidget or QFrame is NoFocus already; saying so at construction
    keeps the intent in the code rather than in the toolkit's defaults.
    """

    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return widget


def follow_overflow(area) -> OverflowFocus:
    """Make `area` a stop exactly while it overflows; the area owns the helper."""

    return OverflowFocus(area)
