"""Seekable QTextEdit for click-to-seek reading position.

This widget emits an absolute character offset (document position) when the user
performs a *click* in the reader. The UI controller can then resolve that offset
to a narration chunk and restart playback using the existing chunk-driven model.

Important: this is intentionally chunk-relative seeking; it does not attempt
sample-accurate audio seeking.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal, Qt
from PySide6.QtWidgets import QTextEdit


class SeekableTextEdit(QTextEdit):
    """A read-only QTextEdit that emits `seek_requested(char_offset)` on click."""

    seek_requested = Signal(int)

    def __init__(self, parent=None, *, click_drag_threshold_px: int = 5) -> None:
        super().__init__(parent)
        self._press_pos: QPoint | None = None
        self._dragging: bool = False
        self._threshold_px = max(0, int(click_drag_threshold_px))

        # UX: make it discoverable that the text is clickable.
        # Keep selection available (dragging), but show a hand cursor on hover.
        try:
            self.viewport().setCursor(Qt.PointingHandCursor)
        except Exception:  # pragma: no cover
            pass

    @staticmethod
    def _mouse_pos(event) -> QPoint:
        """Return a QPoint for the mouse position across Qt bindings."""

        try:
            # Qt6 (PySide6): QMouseEvent.position() -> QPointF
            return event.position().toPoint()
        except Exception:  # pragma: no cover
            try:
                # Qt5-style compatibility: QMouseEvent.pos() -> QPoint
                return event.pos()
            except Exception:
                return QPoint(0, 0)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event is not None and event.button() == Qt.LeftButton:
            self._press_pos = self._mouse_pos(event)
            self._dragging = False
        # Defensive: some tests may call this with None.
        if event is None:  # pragma: no cover
            return
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._press_pos is not None and not self._dragging and event is not None:
            cur = self._mouse_pos(event)
            if (cur - self._press_pos).manhattanLength() > self._threshold_px:
                self._dragging = True
        if event is None:  # pragma: no cover
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Defensive: tests may call this with None.
        if event is None:
            self._press_pos = None
            self._dragging = False
            return

        # Let QTextEdit update cursor/selection first.
        super().mouseReleaseEvent(event)

        try:
            if event.button() != Qt.LeftButton:
                return
            # Preserve typical selection modifier behavior.
            if event.modifiers() != Qt.NoModifier:
                return
            if self._press_pos is None or self._dragging:
                return

            pos = self._mouse_pos(event)
            cursor = self.cursorForPosition(pos)
            self.seek_requested.emit(int(cursor.position()))
        finally:
            self._press_pos = None
            self._dragging = False

