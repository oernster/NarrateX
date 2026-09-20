"""The tile delegate, checked by painting it and reading the pixels back.

A paint that raises and a paint that draws nothing look identical from the
outside, so every assertion here is about pixels that actually landed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QBuffer, QModelIndex, QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.progress import Progress, ReadingState
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.shelf_model import TILE_ROLE, TileData
from voice_reader.ui.shelf_tile import TILE_HEIGHT, TILE_WIDTH, ShelfTileDelegate
from voice_reader.ui.window_helpers import RING_GREEN, RING_RED


def _png(width: int = 60, height: int = 90, colour: int = 0xFF8800) -> bytes:
    picture = QImage(width, height, QImage.Format.Format_RGB32)
    picture.fill(colour)
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, "PNG")
    return bytes(buffer.data())


def _work(title: str = "Dune", author: str = "Frank Herbert") -> Work:
    key = ShelfKey(path=Path("H:/Books") / f"{title}.epub", size_bytes=1, modified_ns=1)
    entry = ShelfEntry(key=key, title=title, author=author)
    return Work(title=title, author=author, entries=(entry,))


class _Covers:
    """The cover service, as the grid uses it: held, wanted, nothing more."""

    def __init__(self, held: dict[str, bytes] | None = None) -> None:
        self._held = held or {}
        self.wanted: list[str] = []

    def held_for(self, work: Work) -> bytes | None:
        return self._held.get(work.token)

    def thumbnail(self, work: Work) -> bytes | None:
        self._held[work.token] = _png()
        return self._held[work.token]

    def arrive(self, work: Work) -> None:
        self._held[work.token] = _png()


# The delegate ------------------------------------------------------------


class _TileModel(QAbstractListModel):
    """One row answering TILE_ROLE, so the delegate paints on a real index.

    A stand-in index cannot be used: the delegate hands anything that is not a
    tile to Qt's own paint, which will not accept one.
    """

    def __init__(self, tile) -> None:
        super().__init__()
        self._tile = tile

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt naming)
        return 0 if parent.isValid() else 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        del index
        return self._tile if role == TILE_ROLE else None


def _painted(tile, *, selected: bool = False) -> QImage:
    """The tile drawn into an image, so the pixels can be read back.

    The painter is ended in a finally: a painter left active on an image that is
    then collected aborts the interpreter, which shows up as a crash in whatever
    test happens to run the next collection.
    """

    canvas = QImage(TILE_WIDTH, TILE_HEIGHT, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    model = _TileModel(tile)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, TILE_WIDTH, TILE_HEIGHT)
    if selected:
        option.state |= QStyle.StateFlag.State_Selected
    painter = QPainter(canvas)
    try:
        ShelfTileDelegate().paint(painter, option, model.index(0, 0))
    finally:
        painter.end()
    return canvas


def _drawn_pixels(canvas: QImage) -> int:
    return sum(
        1
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y).alpha() > 0
    )


def _highlight_pixels(canvas: QImage) -> int:
    """How much of the tile is drawn in the accent colour: the progress bar.

    Counting every drawn pixel cannot see the bar at all, because the tile's own
    surface covers the whole canvas either way. The bar is the only thing painted
    in the palette's highlight, so that is what gets counted.
    """

    from PySide6.QtWidgets import QApplication

    wanted = QApplication.palette().highlight().color().rgb()
    return sum(
        1
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y).rgb() == wanted
    )


def test_a_tile_with_a_picture_draws_something(qapp) -> None:
    del qapp
    picture_bytes = _png(160, 200)
    from PySide6.QtGui import QPixmap

    picture = QPixmap()
    assert picture.loadFromData(picture_bytes)
    tile = TileData(
        title="Dune",
        author="Frank Herbert",
        picture=picture,
        progress=Progress(state=ReadingState.READING, fraction=0.5),
    )

    assert _drawn_pixels(_painted(tile)) > 0


def test_a_tile_with_no_picture_still_draws_its_words(qapp) -> None:
    """FR-BS-033: a placeholder bearing the title and author."""

    del qapp
    from voice_reader.domain.shelf.progress import UNREAD

    tile = TileData(title="Notes", author="Someone", picture=None, progress=UNREAD)

    assert _drawn_pixels(_painted(tile)) > 0
    assert _highlight_pixels(_painted(tile)) == 0, "an unread book fills no bar"


def test_a_selected_tile_is_drawn_differently(qapp) -> None:
    """The ring round the selected tile: the pixels must actually differ."""

    del qapp
    from voice_reader.domain.shelf.progress import UNREAD

    tile = TileData(title="Notes", author="Someone", picture=None, progress=UNREAD)

    assert _painted(tile, selected=True) != _painted(tile)


def test_a_finished_book_fills_more_of_the_bar_than_a_started_one(qapp) -> None:
    del qapp
    started = TileData(
        title="Dune",
        author="Frank Herbert",
        picture=None,
        progress=Progress(state=ReadingState.READING, fraction=0.1),
    )
    finished = TileData(
        title="Dune",
        author="Frank Herbert",
        picture=None,
        progress=Progress(state=ReadingState.FINISHED, fraction=1.0),
    )

    assert _highlight_pixels(_painted(finished)) > _highlight_pixels(_painted(started))
    assert _highlight_pixels(_painted(started)) > 0


def test_something_that_is_not_a_tile_falls_back_to_qt(qapp) -> None:
    """A model answering something else must not stop the shelf drawing."""

    del qapp

    assert _painted("not a tile") is not None


def test_the_size_hint_is_the_tile(qapp) -> None:
    del qapp
    option = QStyleOptionViewItem()
    model = _TileModel(None)

    size = ShelfTileDelegate().sizeHint(option, model.index(0, 0))

    assert (size.width(), size.height()) == (TILE_WIDTH, TILE_HEIGHT)


def test_the_ring_under_the_pointer_is_the_house_green(qapp) -> None:
    """The same green every other control wears, read from its one home."""

    from PySide6.QtGui import QColor

    from voice_reader.ui.window_helpers import RING_GREEN

    del qapp
    from voice_reader.domain.shelf.progress import UNREAD

    tile = TileData(title="Dune", author="Frank Herbert", picture=None, progress=UNREAD)
    wanted = QColor(RING_GREEN).rgb()

    ringed = _painted(tile, selected=True)
    plain = _painted(tile)

    def _count(canvas):
        return sum(
            1
            for y in range(canvas.height())
            for x in range(canvas.width())
            if canvas.pixelColor(x, y).rgb() == wanted
        )

    assert _count(ringed) > 0, "a marked tile draws the green ring"
    assert _count(plain) == 0, "an unmarked tile draws no ring at all"


# The locked ring (FR-BS-055a) ---------------------------------------------


def _ring_pixels(canvas: QImage, colour: str) -> int:
    """How many pixels of the tile were drawn in one ring colour."""

    from PySide6.QtGui import QColor

    wanted = QColor(colour).rgb()
    return sum(
        1
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixelColor(x, y).rgb() == wanted
    )


def _painted_marked(tile, *, locked: bool) -> QImage:
    """A tile drawn with the pointer on it, locked or not."""

    canvas = QImage(TILE_WIDTH, TILE_HEIGHT, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    model = _TileModel(tile)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, TILE_WIDTH, TILE_HEIGHT)
    option.state |= QStyle.StateFlag.State_MouseOver
    delegate = ShelfTileDelegate()
    delegate.set_locked(locked)
    painter = QPainter(canvas)
    try:
        delegate.paint(painter, option, model.index(0, 0))
    finally:
        painter.end()
    return canvas


def _plain_tile() -> TileData:
    return TileData(
        title="Dune",
        author="Frank Herbert",
        picture=None,
        progress=Progress(state=ReadingState.UNREAD, fraction=0.0),
    )


def test_the_pointer_rings_a_tile_green_while_a_book_can_be_opened(qapp) -> None:
    del qapp
    canvas = _painted_marked(_plain_tile(), locked=False)

    assert _ring_pixels(canvas, RING_GREEN) > 0
    assert _ring_pixels(canvas, RING_RED) == 0


def test_the_pointer_rings_a_tile_red_while_the_engine_is_narrating(qapp) -> None:
    """FR-BS-055a: no green ring offering a click that will be refused."""

    del qapp
    canvas = _painted_marked(_plain_tile(), locked=True)

    assert _ring_pixels(canvas, RING_RED) > 0
    assert _ring_pixels(canvas, RING_GREEN) == 0
