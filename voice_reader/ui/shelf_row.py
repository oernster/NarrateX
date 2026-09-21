"""Drawing one row: a small cover, the words across, the progress at the end.

FR-BS-051. The row is the tile laid on its side, so it is drawn by the tile's
own pieces: the lifted surface with its ring, the cover, one line of words cut
short to fit, the state with its bar. Only the places they go are this module's;
a row that drew any of them its own way would be a second shelf able to disagree
with the first about what a locked ring looks like.

What a row has that a tile has not is width, so it spends it on the genres: the
one thing FR-BS-051 asks of a row that a tile never showed.

**A row's height is read off its fonts, never written down.** Three lines of
words with the gaps between them, the padding round them and the inset the ring
needs. A number standing in for that would be right at one font size and wrong
at every other, silently.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QFontMetrics, QPainter

from voice_reader.ui.shelf_model import TILE_ROLE, TileData
from voice_reader.ui.shelf_tile import (
    INSET,
    LINE_GAP,
    PADDING,
    ShelfTileDelegate,
    loud_colour,
    quiet_colour,
    quiet_font,
    title_font,
)

# The gap between two rows.
ROW_GAP = 4

# A cover is taller than it is wide; this is the proportion of a paperback, so a
# row's picture reads as a book rather than as a square thumbnail.
_COVER_ASPECT = 2 / 3
# The column the progress sits in at the row's right-hand end. Wide enough for
# "Finished" with room either side, so the word never runs into the next column.
_PROGRESS_WIDTH = 120

# What a row says where a work states no genre. The filter dialog calls the same
# thing "Books that state no genre", so this is that phrase for one book.
NO_GENRE_TEXT = "No genre stated"
# Several genres read as one line, the way a list is written in prose.
GENRE_JOIN = ", "


class ShelfRowDelegate(ShelfTileDelegate):
    """Draws a work as a row: small cover, title, author, genres, progress."""

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 (Qt naming)
        del index
        return QSize(option.rect.width(), row_height(option))

    def paint(self, painter: QPainter, option, index) -> None:
        tile = index.data(TILE_ROLE)
        if not isinstance(tile, TileData):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = option.rect.adjusted(INSET, INSET, -INSET, -INSET)
        self._panel(painter, option, body)

        inner_height = body.height() - 2 * PADDING
        cover = QRect(
            body.left() + PADDING,
            body.top() + PADDING,
            int(inner_height * _COVER_ASPECT),
            inner_height,
        )
        self._cover(painter, option, cover, tile)

        progress = QRect(
            body.right() - PADDING - _PROGRESS_WIDTH,
            cover.top(),
            _PROGRESS_WIDTH,
            inner_height,
        )
        self._progress(painter, option, progress, progress.top(), tile)

        words = QRect(
            cover.right() + PADDING,
            cover.top(),
            progress.left() - cover.right() - 2 * PADDING,
            inner_height,
        )
        self._row_words(painter, option, words, tile)
        painter.restore()

    def _placeholder(
        self, painter: QPainter, option, cover: QRect, tile: TileData
    ) -> None:
        """FR-BS-033 in a row: the well alone.

        A tile writes the title and author into an empty cover because that is
        the only place it has for them. A row prints both beside the cover
        already, so writing them into a well a third of the width would say
        the same thing twice, the second time too small to read.
        """

        del tile
        self._well(painter, option, cover)

    def _row_words(
        self, painter: QPainter, option, words: QRect, tile: TileData
    ) -> None:
        """Title, then author, then what the work is filed under."""

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
        self._line(
            painter,
            words,
            author.bottom() + LINE_GAP,
            genre_words(tile.genres),
            quiet_font(option),
            quiet_colour(option),
        )


def row_height(option) -> int:
    """How tall a row is at the view's font: three lines and what surrounds them."""

    title = QFontMetrics(title_font(option)).height()
    quiet = QFontMetrics(quiet_font(option)).height()
    lines = title + 2 * quiet + 2 * LINE_GAP
    return lines + 2 * PADDING + 2 * INSET


def genre_words(genres: tuple[str, ...]) -> str:
    """The genres as one line; a plain statement where there are none."""

    return GENRE_JOIN.join(genres) if genres else NO_GENRE_TEXT
