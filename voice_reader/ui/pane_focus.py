"""A scrolling region is a keyboard stop only while it has somewhere to scroll.

A pane is chrome, not a control: Tab landing on text that fits its viewport is
one dead press before the control the reader wanted. But a long read-only page
with no controls of its own must stay reachable; otherwise the keyboard cannot scroll
it. So the region's focus follows its overflow, re-decided every time either
scrollbar's range changes (content loaded, dialog resized). Its viewport is a
separate focusable child and is never a stop.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt


class OverflowFocus(QObject):
    def __init__(self, area, *, overflow_policy=Qt.FocusPolicy.StrongFocus) -> None:
        super().__init__(area)
        self._area = area
        self._overflow_policy = overflow_policy
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
            self._overflow_policy if self.overflows() else Qt.FocusPolicy.NoFocus
        )


def follow_overflow(area, **kwargs) -> OverflowFocus:
    """Make `area` a stop exactly while it overflows; the area owns the helper."""

    return OverflowFocus(area, **kwargs)
