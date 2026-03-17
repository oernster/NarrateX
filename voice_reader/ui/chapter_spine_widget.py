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
    playhead_color: QColor = field(default_factory=lambda: QColor("#f97316"))
    playhead_alpha: int = 235
    rail_width: int = 2
    marker_width: int = 2
    marker_highlight_width: int = 3
    playhead_width: int = 3
    marker_len: int = 10
    padding: int = 8


class ChapterSpineWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style = _SpineStyle()
        self._chapters: list[Chapter] = []
        self._current: Chapter | None = None
        self._playhead_char_offset: int | None = None

        self.setFixedWidth(22)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_chapters(self, chapters: Sequence[Chapter]) -> None:
        self._chapters = list(chapters)
        self.update()

    def set_current_chapter(self, chapter: Chapter | None) -> None:
        self._current = chapter
        self.update()

    def set_playhead_char_offset(self, char_offset: int | None) -> None:
        """Set the live playback position (char offset) for a horizontal playhead.

        This is intentionally independent from the "current chapter" marker:
        - current chapter snaps to the nearest chapter boundary
        - playhead can move continuously during playback
        
        If called with None, the playhead is cleared.
        """

        self._playhead_char_offset = None if char_offset is None else int(char_offset)
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

        # Playhead (live playback position): contrasting horizontal line.
        # Draw last so it remains visible even when aligned with a chapter marker.
        if self._playhead_char_offset is not None:
            y = self._y_for_char_offset(
                top=top,
                bottom=bottom,
                char_offset=int(self._playhead_char_offset),
            )
            col = QColor(self._style.playhead_color)
            col.setAlpha(int(self._style.playhead_alpha))
            p.setPen(QPen(col, int(self._style.playhead_width)))
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

    def _y_for_char_offset(self, *, top: int, bottom: int, char_offset: int) -> int:
        """Map an absolute char offset into the spine's vertical rail geometry.

        We normalize using the min/max chapter offsets. This keeps the playhead in
        the same "chapter distribution" space as the markers, and clamps outside
        the first/last chapter.
        """

        if not self._chapters or len(self._chapters) <= 1:
            return int((top + bottom) // 2)

        offsets = [int(c.char_offset) for c in self._chapters]
        lo = min(offsets)
        hi = max(offsets)
        span = max(1, hi - lo)
        height = max(1, bottom - top)

        t = float(int(char_offset) - lo) / float(span)
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        return int(round(top + t * height))
