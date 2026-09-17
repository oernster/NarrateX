"""A dialog that opens focused on its first control, never on a reading pane.

Ported from Stellody's FirstStopDialog (ClearBudget carries the same one).

Left to itself, Qt focuses a dialog's first Tab stop as it opens. Where that
stop is a reading pane (a licence, the Guide) the dialog opened with the ring
round the whole page before anybody had done anything: it outlines everything
while offering nothing to act on. So the dialog picks its own opening stop by
walking the toolkit's OWN focus chain. It passes over anything disabled, hidden
or refusing tab focus; it passes over every scroll area too. The pane keeps its
stop, so a long text stays readable from the keyboard; it is simply not what
the dialog opens on.

A subclass that overrides `showEvent` must call `super()`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractScrollArea, QDialog, QWidget


class FirstStopDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._started = False

    def first_stop(self) -> QWidget | None:
        """The control the first Tab press would reach; None where there is none."""

        widget, seen = self.nextInFocusChain(), set()
        while widget is not None and id(widget) not in seen:
            seen.add(id(widget))
            if (
                widget is not self
                and self.isAncestorOf(widget)
                and widget.isEnabled()
                and widget.isVisible()
                and not isinstance(widget, QAbstractScrollArea)
                and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
            ):
                return widget
            widget = widget.nextInFocusChain()
        return None

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Focus the first stop the first time the dialog opens."""

        super().showEvent(event)
        if self._started:
            return
        self._started = True
        stop = self.first_stop()
        if stop is not None:
            # The tab reason, so it wears the same ring a tabbed-to control
            # wears rather than a different-looking one.
            stop.setFocus(Qt.FocusReason.TabFocusReason)
