"""Gentle auto-scroll for long content a reader reads through.

The cycle holds still when the surface opens, reads down slowly, holds at the
bottom so the tail can be read, rewinds fast, holds briefly and starts over.
Manual reading (wheel, click, keys, the scrollbar, focus moving inside) only
suspends it: after a moment of stillness it resumes from wherever the reader
left it. While a modal dialog sits above the surface it freezes in place and
takes no input, so it comes back exactly as it was.

Ported from Fulcrum's `auto_scroller.py`; the constants are the portfolio's one
reading pace and belong to this class, never to a dialog. Surfaces to READ
THROUGH wear it (the Guide, the licences); the book in the reading pane is the
reader's own to pace and does not.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QWidget


class AutoScroller(QObject):
    TICK_MS = 40
    DOWN_STEP_PX = 1
    # One step every second tick: the standard reading pace.
    DOWN_TICKS_PER_STEP = 2
    # The rewind is a reposition, not a reading pass, so it travels fast.
    UP_STEP_PX = 15
    START_PAUSE_MS = 5000
    BOTTOM_PAUSE_MS = 5000
    TOP_PAUSE_MS = 2000
    RESUME_AFTER_MS = 2500

    DOWN = "down"
    UP = "up"
    PAUSE_TOP = "pause_top"
    PAUSE_BOTTOM = "pause_bottom"
    MANUAL = "manual"
    _WAITING = (PAUSE_TOP, PAUSE_BOTTOM, MANUAL)
    _MANUAL_EVENTS = (
        QEvent.Type.Wheel,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.KeyPress,
    )

    def __init__(self, area) -> None:
        super().__init__(area)
        self._area = area
        self._bar = area.verticalScrollBar()
        self._down_countdown = self.DOWN_TICKS_PER_STEP
        self.phase = self.PAUSE_TOP
        self._wait_ms = self.START_PAUSE_MS
        # The dialog focusing its own text as it opens is not a reader taking
        # hold; focus arrivals are ignored until the start hold is spent.
        self._opening = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.TICK_MS)
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        self._bar.sliderPressed.connect(self.suspend)
        self._bar.sliderReleased.connect(self.suspend)
        self._bar.sliderMoved.connect(lambda _value: self.suspend())
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def suspend(self) -> None:
        """Hand the content to the reader and count down to resuming."""

        # A frozen surface has no reader: the toolkit's own resets on the way
        # out of a modal must not read as a hand taking over.
        if self._frozen_under_modal():
            return
        self._opening = False
        self.phase = self.MANUAL
        self._wait_ms = self.RESUME_AFTER_MS

    def _on_focus_changed(self, _old, new) -> None:
        if self._opening:
            return
        if isinstance(new, QWidget) and (
            new is self._area or self._area.isAncestorOf(new)
        ):
            self.suspend()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() in self._MANUAL_EVENTS:
            self.suspend()
        return False

    def _frozen_under_modal(self) -> bool:
        modal = QApplication.activeModalWidget()
        if modal is None:
            return False
        return not (modal is self._area.window() or modal.isAncestorOf(self._area))

    def tick(self) -> None:
        if self._frozen_under_modal():
            return
        maximum = self._bar.maximum()
        if maximum <= 0:
            return
        if self.phase in self._WAITING:
            self._wait_ms -= self.TICK_MS
            if self._wait_ms <= 0:
                self._opening = False
                self.phase = self._resumed_phase(maximum)
            return
        if self.phase == self.DOWN:
            self._down_countdown -= 1
            if self._down_countdown > 0:
                return
            self._down_countdown = self.DOWN_TICKS_PER_STEP
            value = self._bar.value() + self.DOWN_STEP_PX
            if value >= maximum:
                self._bar.setValue(maximum)
                self.phase = self.PAUSE_BOTTOM
                self._wait_ms = self.BOTTOM_PAUSE_MS
            else:
                self._bar.setValue(value)
            return
        value = self._bar.value() - self.UP_STEP_PX
        if value <= 0:
            self._bar.setValue(0)
            self.phase = self.PAUSE_TOP
            self._wait_ms = self.TOP_PAUSE_MS
        else:
            self._bar.setValue(value)

    def _resumed_phase(self, maximum: int) -> str:
        if self.phase == self.PAUSE_BOTTOM:
            return self.UP
        if self.phase == self.MANUAL and self._bar.value() >= maximum:
            return self.UP
        return self.DOWN
