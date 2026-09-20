"""The grid of tiles: a view over the model, with its pictures arriving late.

FR-BS-050 and FR-BS-037. A `QListView` in icon mode holds no widget per work, so
the shelf costs the same at three thousand works as at thirty; the delegate beside
it draws each tile.

**A pane is not a keyboard stop, yet a grid is.** The rule the shelf follows is
that a container holding controls takes no focus and paints no ring; this view is
not a container, it is the control; a reader has to be able to reach the works
with the keyboard (FR-BS-059). It therefore takes focus as the reader, the list in
the Bookmarks dialog and every other real control does.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QListView, QWidget

from voice_reader.domain.shelf.progress import Progress
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.shelf_cover_loader import ShelfCoverLoader
from voice_reader.ui.shelf_model import ShelfModel
from voice_reader.ui.shelf_tile import (
    TILE_GAP,
    TILE_HEIGHT,
    TILE_WIDTH,
    ShelfTileDelegate,
)


class ShelfGrid(QListView):
    """Every work as a tile, drawn by the delegate, filled in the background."""

    work_activated = Signal(object)

    def __init__(
        self,
        *,
        covers=None,
        progress_of: Callable[[Work], Progress] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = ShelfCoverLoader(covers, parent=self) if covers else None
        self._model = ShelfModel(
            held_picture=covers.held_for if covers else _no_picture,
            progress_of=progress_of,
            want_picture=self._loader.want if self._loader else None,
            parent=self,
        )
        self.setModel(self._model)
        self.setItemDelegate(ShelfTileDelegate(self))
        self._configure()
        if self._loader is not None:
            # A bound method of a QObject living on this thread, so Qt queues
            # the call rather than running it on the worker that emitted it.
            self._loader.picture_ready.connect(self._model.picture_arrived)
        self.activated.connect(self._on_activated)

    def _configure(self) -> None:
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setSpacing(TILE_GAP)
        self.setGridSize(QSize(TILE_WIDTH + TILE_GAP, TILE_HEIGHT + TILE_GAP))
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setFrameShape(QListView.Shape.NoFrame)
        # The tiles carry the shelf's surfaces; a viewport painting its own
        # would put a second background behind them.
        self.viewport().setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # What the controller says ---------------------------------------------

    def show_works(self, works: tuple[Work, ...]) -> None:
        self._model.set_works(works)

    def works(self) -> tuple[Work, ...]:
        return self._model.works()

    def selected_work(self) -> Work | None:
        indexes = self.selectedIndexes()
        if not indexes:
            return None
        return self._model.work_at(indexes[0])

    def release(self) -> None:
        """Stop the background reader. Called when the window is closing."""

        if self._loader is not None:
            self._loader.stop()

    # Qt ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Enter and Space open the tile that has the ring (FR-BS-059)."""

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            work = self.selected_work() or self._model.work_at(self.currentIndex())
            if work is not None:
                self.work_activated.emit(work)
                return
        super().keyPressEvent(event)

    def _on_activated(self, index) -> None:
        work = self._model.work_at(index)
        if work is not None:
            self.work_activated.emit(work)


def _no_picture(_work: Work) -> bytes | None:
    """The answer where no cover service was wired: every tile a placeholder."""

    return None
