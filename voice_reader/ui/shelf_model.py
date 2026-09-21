"""What the grid asks about one work; where the pictures are held.

The grid is a view over a model rather than a field of widgets, so the number of
live tile widgets is zero however many works the shelf holds (FR-BS-037). What
does grow with the collection is the pictures, so they are held in a bounded
cache: the oldest is dropped when a new one arrives; dropping one costs a
decode rather than a read of the book.

**A paint never waits on a disk.** The model answers a picture only where one is
already decoded or already cached on disk; anything else is asked for in the
background and arrives on a later paint (FR-BS-038).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QPixmap

from voice_reader.domain.shelf.progress import UNREAD, Progress
from voice_reader.domain.shelf.works import Work

# One role: the delegate wants the whole tile at once; a role per field
# would have it ask the model five times to paint one tile.
TILE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

# How many decoded pictures are held. At the drawn size a picture costs about
# 150 KB, so this is roughly 30 MB: several screenfuls in every direction,
# which is what makes scrolling back up free.
PIXMAP_CACHE_SIZE = 200


@dataclass(frozen=True, slots=True)
class TileData:
    """Everything one tile draws, gathered once per paint."""

    title: str
    author: str
    picture: QPixmap | None
    progress: Progress
    #: Drawn by a row, which has the width for it (FR-BS-051); a tile does not.
    genres: tuple[str, ...] = ()


class ShelfModel(QAbstractListModel):
    """The works on the shelf, in the order the shelf asked for them."""

    def __init__(
        self,
        *,
        held_picture: Callable[[Work], bytes | None],
        progress_of: Callable[[Work], Progress] | None = None,
        want_picture: Callable[[Work], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._works: tuple[Work, ...] = ()
        self._held_picture = held_picture
        self._progress_of = progress_of
        self._want_picture = want_picture
        self._pixmaps: OrderedDict[str, QPixmap] = OrderedDict()

    # The works ------------------------------------------------------------

    def set_works(self, works: tuple[Work, ...]) -> None:
        """Replace the shelf. The pictures already decoded are kept."""

        self.beginResetModel()
        self._works = tuple(works)
        self.endResetModel()

    def works(self) -> tuple[Work, ...]:
        return self._works

    def work_at(self, index: QModelIndex) -> Work | None:
        row = index.row()
        if 0 <= row < len(self._works):
            return self._works[row]
        return None

    def picture_arrived(self, token: str) -> None:
        """A background read finished; redraw the rows that were waiting.

        The row is found by token rather than remembered, because the shelf may
        have been re-ordered or refiltered while the picture was being read.
        """

        self._pixmaps.pop(token, None)
        for row, work in enumerate(self._works):
            if work.token == token:
                where = self.index(row, 0)
                self.dataChanged.emit(where, where, [TILE_ROLE])

    def forget_pictures(self) -> None:
        self._pixmaps.clear()

    # What Qt asks ---------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt naming)
        if parent.isValid():
            return 0
        return len(self._works)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        work = self.work_at(index)
        if work is None:
            return None
        if role == TILE_ROLE:
            return self._tile(work)
        if role == Qt.ItemDataRole.DisplayRole:
            return work.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{work.title}\n{work.author}" if work.author else work.title
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{work.title} by {work.author}" if work.author else work.title
        return None

    # Internals ------------------------------------------------------------

    def _tile(self, work: Work) -> TileData:
        return TileData(
            title=work.title,
            author=work.author,
            picture=self._picture(work),
            progress=self._progress(work),
            genres=work.genres,
        )

    def _picture(self, work: Work) -> QPixmap | None:
        token = work.token
        decoded = self._pixmaps.get(token)
        if decoded is not None:
            self._pixmaps.move_to_end(token)
            return decoded
        image = self._held_picture(work)
        if image is None:
            if self._want_picture is not None:
                self._want_picture(work)
            return None
        picture = QPixmap()
        if not picture.loadFromData(image):
            return None
        self._pixmaps[token] = picture
        while len(self._pixmaps) > PIXMAP_CACHE_SIZE:
            self._pixmaps.popitem(last=False)
        return picture

    def _progress(self, work: Work) -> Progress:
        if self._progress_of is None:
            return UNREAD
        return self._progress_of(work)
