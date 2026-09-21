"""Drawing one tile: the cover, the words and how far through it the reader is.

FR-BS-050, FR-BS-033 and FR-BS-054. A delegate rather than a widget per work, so
a shelf of three thousand costs the same as a shelf of thirty (FR-BS-037).

**No colour is invented here.** The greys come from the palette, which the one
stylesheet fills; the ring under the pointer is the same green every other
control in the window wears, read from where that green is declared. A delegate
naming its own colours would be a second theme able to drift from the first.

**A locked shelf rings red** (FR-BS-055a). While the engine is narrating, no
other book can be opened, so a green ring under the pointer would offer a click
that is going to be refused. Red is what this window already puts on a control
that is shut, so the shelf says the same thing the open control beside it says.

A work with no picture is not a gap: it draws its title and author in the cover's
place and stays selectable (FR-BS-033).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from voice_reader.domain.shelf.progress import ReadingState
from voice_reader.ui.shelf_model import TILE_ROLE, TileData
from voice_reader.ui.window_helpers import RING_GREEN, RING_RED

TILE_WIDTH = 176
TILE_HEIGHT = 310
TILE_GAP = 10

PADDING = 8
# How far a surface sits inside the box Qt gives it, so a ring has room.
INSET = 2
_COVER_HEIGHT = 200
LINE_GAP = 2
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._locked = False

    def set_locked(self, locked: bool) -> None:
        """Say whether a book can be opened at all; the ring follows."""

        self._locked = locked

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
        body = option.rect.adjusted(INSET, INSET, -INSET, -INSET)
        self._panel(painter, option, body)

        cover = QRect(
            body.left() + PADDING,
            body.top() + PADDING,
            body.width() - 2 * PADDING,
            _COVER_HEIGHT,
        )
        self._cover(painter, option, cover, tile)

        words = QRect(
            cover.left(),
            cover.bottom() + PADDING,
            cover.width(),
            body.bottom() - cover.bottom() - 2 * PADDING,
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
            ring = RING_RED if self._locked else RING_GREEN
            painter.setPen(QPen(QColor(ring), _RING_WIDTH))
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

        self._well(painter, option, cover)
        painter.setPen(quiet_colour(option))
        inner = cover.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        words = tile.title if not tile.author else f"{tile.title}\n{tile.author}"
        painter.drawText(
            inner,
            int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
            words,
        )

    @staticmethod
    def _well(painter: QPainter, option, cover: QRect) -> None:
        """The sunken place a cover sits in, drawn where there is no cover."""

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(option.palette.window().color().darker(_WELL_DEPTH))
        painter.drawRoundedRect(cover, _CORNER_RADIUS, _CORNER_RADIUS)

    def _words(self, painter: QPainter, option, words: QRect, tile: TileData) -> None:
        title = self._line(
            painter,
            words,
            words.top(),
            tile.title,
            title_font(option),
            loud_colour(option),
        )
        author = self._line(
            painter,
            words,
            title.bottom() + LINE_GAP,
            tile.author,
            quiet_font(option),
            quiet_colour(option),
        )
        self._progress(painter, option, words, author.bottom() + LINE_GAP, tile)

    @staticmethod
    def _line(
        painter: QPainter,
        column: QRect,
        top: int,
        text: str,
        font: QFont,
        colour: QColor,
    ) -> QRect:
        """One line of words across `column` from `top`, cut short to fit.

        Answers the rect it filled, so the line under it knows where to start.
        Shared by the tile and the row, which differ in where their lines go
        and never in how one is drawn.
        """

        painter.setFont(font)
        painter.setPen(colour)
        rect = QRect(column.left(), top, column.width(), painter.fontMetrics().height())
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            painter.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, column.width()
            ),
        )
        return rect

    def _progress(
        self, painter: QPainter, option, column: QRect, top: int, tile: TileData
    ) -> None:
        """FR-BS-054: the state in a word from `top`, with a bar under it."""

        state_rect = self._line(
            painter,
            column,
            top,
            _STATE_WORDS[tile.progress.state],
            quiet_font(option),
            quiet_colour(option),
        )

        track = QRect(
            column.left(),
            state_rect.bottom() + LINE_GAP,
            column.width(),
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


def loud_colour(option) -> QColor:
    """The colour of a first line: the palette's own text."""

    return option.palette.text().color()


def quiet_colour(option) -> QColor:
    """The colour of every line under the first."""

    return _dimmed(option.palette.text().color())


def title_font(option) -> QFont:
    """The first line's face: the view's own, in bold."""

    font = QFont(option.font)
    font.setBold(True)
    base_size = option.font.pointSize()
    if base_size > 0:
        font.setPointSize(base_size + _TITLE_POINT_DELTA)
    return font


def quiet_font(option) -> QFont:
    """Every other line's face: a point smaller than the view's own."""

    font = QFont(option.font)
    base_size = option.font.pointSize()
    if base_size > 0:
        font.setPointSize(max(1, base_size + _AUTHOR_POINT_DELTA))
    return font
