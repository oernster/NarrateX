"""UI widget: a minimal vertical chapter spine.

The spine is a calm visual rail beside the reader pane:
- narrow teal line
- dash markers per chapter
- current chapter marker highlighted

No chapter persistence; this widget is purely presentational.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from voice_reader.domain.entities.chapter import Chapter


@dataclass(frozen=True, slots=True)
class _SpineStyle:
    rail_color: QColor = field(default_factory=lambda: QColor("#14b8a6"))
    rail_alpha: int = 110
    marker_alpha: int = 160
    marker_highlight_alpha: int = 255
    rail_width: int = 2
    marker_width: int = 2
    marker_highlight_width: int = 3
    marker_len: int = 10
    padding: int = 8


class ChapterSpineWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style = _SpineStyle()
        self._chapters: list[Chapter] = []
        self._current: Chapter | None = None

        self.setFixedWidth(22)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_chapters(self, chapters: Sequence[Chapter]) -> None:
        self._chapters = list(chapters)
        self.update()

    def set_current_chapter(self, chapter: Chapter | None) -> None:
        self._current = chapter
        self.update()

    def _set_style_for_tests(self, *, padding: int | None = None) -> None:
        """Test-only helper to cover style edge branches."""

        if padding is not None:
            # `_SpineStyle` is frozen; bypass immutability for deterministic tests.
            object.__setattr__(self._style, "padding", int(padding))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = int(self.width())
        h = int(self.height())
        x = int(w // 2)

        top = int(self._style.padding)
        bottom = int(h - self._style.padding)
        if bottom <= top:
            return

        # Rail.
        rail = QColor(self._style.rail_color)
        rail.setAlpha(int(self._style.rail_alpha))
        p.setPen(QPen(rail, int(self._style.rail_width)))
        p.drawLine(x, top, x, bottom)

        if not self._chapters:
            return

        y_positions = self._y_positions(top=top, bottom=bottom)

        for ch, y in zip(self._chapters, y_positions, strict=False):
            highlight = self._current is not None and ch == self._current
            col = QColor(self._style.rail_color)
            col.setAlpha(
                int(
                    self._style.marker_highlight_alpha
                    if highlight
                    else self._style.marker_alpha
                )
            )
            width = (
                int(self._style.marker_highlight_width)
                if highlight
                else int(self._style.marker_width)
            )
            p.setPen(QPen(col, width))
            p.drawLine(x, int(y), x + int(self._style.marker_len), int(y))

    def _y_positions(self, *, top: int, bottom: int) -> list[int]:
        n = len(self._chapters)
        if n <= 1:
            return [int((top + bottom) // 2)]

        offsets = [int(c.char_offset) for c in self._chapters]
        lo = min(offsets)
        hi = max(offsets)
        span = max(1, hi - lo)
        height = max(1, bottom - top)

        ys: list[int] = []
        for off in offsets:
            t = float(off - lo) / float(span)
            ys.append(int(round(top + t * height)))
        return ys

