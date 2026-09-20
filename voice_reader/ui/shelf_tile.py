"""Drawing one tile: the cover, the words and how far through it the reader is.

FR-BS-050, FR-BS-033 and FR-BS-054. A delegate rather than a widget per work, so
a shelf of three thousand costs the same as a shelf of thirty (FR-BS-037).

**No colour is invented here.** The greys come from the palette, which the one
stylesheet fills; the ring under the pointer is the same green every other
control in the window wears, read from where that green is declared. A delegate
naming its own colours would be a second theme able to drift from the first.

A work with no picture is not a gap: it draws its title and author in the cover's
place and stays selectable (FR-BS-033).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from voice_reader.domain.shelf.progress import ReadingState
from voice_reader.ui.shelf_model import TILE_ROLE, TileData
from voice_reader.ui.window_helpers import RING_GREEN

TILE_WIDTH = 176
TILE_HEIGHT = 310
TILE_GAP = 10

_PADDING = 8
_COVER_HEIGHT = 200
_LINE_GAP = 2
_BAR_HEIGHT = 5
_CORNER_RADIUS = 6
# The ring is two pixels, as the stylesheet draws it on every other control.
_RING_WIDTH = 2
_TITLE_POINT_DELTA = 0
_AUTHOR_POINT_DELTA = -1

# How far the tile's surface stands out from the window; how far the cover
# well and the progress track sink into it. Both are adjustments to the palette's
# own colours rather than colours of their own, so a theme change carries.
_PANEL_LIFT = 108
_WELL_DEPTH = 108

# The alpha a secondary line of words carries: the author, the state and the
# placeholder lettering, all quieter than the title without being a second grey.
_SECONDARY_ALPHA = 160

_STATE_WORDS = {
    ReadingState.UNREAD: "Unread",
    ReadingState.READING: "Reading",
    ReadingState.FINISHED: "Finished",
}


class ShelfTileDelegate(QStyledItemDelegate):
    """Draws a work as a tile: picture, title, author, progress."""

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 (Qt naming)
        del option, index
        return QSize(TILE_WIDTH, TILE_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        tile = index.data(TILE_ROLE)
        if not isinstance(tile, TileData):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = option.rect.adjusted(2, 2, -2, -2)
        self._panel(painter, option, body)

        cover = QRect(
            body.left() + _PADDING,
            body.top() + _PADDING,
            body.width() - 2 * _PADDING,
            _COVER_HEIGHT,
        )
        self._cover(painter, option, cover, tile)

        words = QRect(
            cover.left(),
            cover.bottom() + _PADDING,
            cover.width(),
            body.bottom() - cover.bottom() - 2 * _PADDING,
        )
        self._words(painter, option, words, tile)
        painter.restore()

    # The pieces -----------------------------------------------------------

    def _panel(self, painter: QPainter, option, body: QRect) -> None:
        """The tile's own surface, lifted from the window behind it."""

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(option.palette.base().color().lighter(_PANEL_LIFT))
        painter.drawRoundedRect(body, _CORNER_RADIUS, _CORNER_RADIUS)
        marked = QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver
        if option.state & marked:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(RING_GREEN), _RING_WIDTH))
            painter.drawRoundedRect(body, _CORNER_RADIUS, _CORNER_RADIUS)

    def _cover(self, painter: QPainter, option, cover: QRect, tile: TileData) -> None:
        if tile.picture is not None and not tile.picture.isNull():
            drawn = tile.picture.scaled(
                cover.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            where = QRect(
                cover.left() + (cover.width() - drawn.width()) // 2,
                cover.top() + (cover.height() - drawn.height()) // 2,
                drawn.width(),
                drawn.height(),
            )
            painter.drawPixmap(where, drawn)
            return
        self._placeholder(painter, option, cover, tile)

    def _placeholder(
        self, painter: QPainter, option, cover: QRect, tile: TileData
    ) -> None:
        """FR-BS-033: no picture, so the words take the picture's place."""

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(option.palette.window().color().darker(_WELL_DEPTH))
        painter.drawRoundedRect(cover, _CORNER_RADIUS, _CORNER_RADIUS)
        painter.setPen(_dimmed(option.palette.text().color()))
        inner = cover.adjusted(_PADDING, _PADDING, -_PADDING, -_PADDING)
        words = tile.title if not tile.author else f"{tile.title}\n{tile.author}"
        painter.drawText(
            inner,
            int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
            words,
        )

    def _words(self, painter: QPainter, option, words: QRect, tile: TileData) -> None:
        metrics_font = QFont(option.font)
        metrics_font.setBold(True)
        base_size = option.font.pointSize()
        if base_size > 0:
            metrics_font.setPointSize(base_size + _TITLE_POINT_DELTA)
        painter.setFont(metrics_font)
        painter.setPen(option.palette.text().color())
        line_height = painter.fontMetrics().height()
        title_rect = QRect(words.left(), words.top(), words.width(), line_height)
        painter.drawText(
            title_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            painter.fontMetrics().elidedText(
                tile.title, Qt.TextElideMode.ElideRight, words.width()
            ),
        )

        author_font = QFont(option.font)
        if base_size > 0:
            author_font.setPointSize(max(1, base_size + _AUTHOR_POINT_DELTA))
        painter.setFont(author_font)
        painter.setPen(_dimmed(option.palette.text().color()))
        author_rect = QRect(
            words.left(),
            title_rect.bottom() + _LINE_GAP,
            words.width(),
            painter.fontMetrics().height(),
        )
        painter.drawText(
            author_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            painter.fontMetrics().elidedText(
                tile.author, Qt.TextElideMode.ElideRight, words.width()
            ),
        )

        self._progress(painter, option, words, author_rect, tile)

    def _progress(
        self, painter: QPainter, option, words: QRect, above: QRect, tile: TileData
    ) -> None:
        """FR-BS-054: the state in a word, with a bar for the fraction."""

        painter.setPen(_dimmed(option.palette.text().color()))
        state_rect = QRect(
            words.left(),
            above.bottom() + _LINE_GAP,
            words.width(),
            painter.fontMetrics().height(),
        )
        painter.drawText(
            state_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            _STATE_WORDS[tile.progress.state],
        )

        track = QRect(
            words.left(),
            state_rect.bottom() + _LINE_GAP,
            words.width(),
            _BAR_HEIGHT,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(option.palette.window().color().darker(_WELL_DEPTH))
        painter.drawRect(track)
        filled = int(round(track.width() * tile.progress.fraction))
        if filled <= 0:
            return
        painter.setBrush(option.palette.highlight().color())
        painter.drawRect(QRect(track.left(), track.top(), filled, track.height()))


def _dimmed(colour: QColor) -> QColor:
    """The palette's text colour, quietened for a secondary line."""

    dimmed = QColor(colour)
    dimmed.setAlpha(_SECONDARY_ALPHA)
    return dimmed
