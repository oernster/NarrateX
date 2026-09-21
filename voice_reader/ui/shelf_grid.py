"""The grid of tiles: a view over the model, with its pictures arriving late.

FR-BS-050 and FR-BS-037. A `QListView` in icon mode holds no widget per work, so
the shelf costs the same at three thousand works as at thirty; the delegate beside
it draws each tile.

**One click opens a book.** The tile under the pointer wears the same green ring
every other control in the window wears; a single left click on it opens the
work, because there is nothing a reader can do with a selected tile that would justify
asking for a second click.

**Except while the engine is narrating** (FR-BS-055a), when the ring turns red
and the click is refused by the controller, which is what can say so and can
read the narration state. The grid holds the fact and paints it; it does not
decide it.

**A plain click opens a book; a click holding Ctrl or Shift gathers one.**
Both reach `clicked`, so the modifier is what tells them apart. Without that
test, building a selection would open every book it touched.

**The right button says what a book is** (FR-BS-046). A book the files say
nothing about is filed by the reader instead, the tile being where they are
looking when they decide; measured, 1251 of 2784 Kindle files state no subject
at all. The menu names the work so a mis-aimed click is visible before it acts.

**A pane is not a keyboard stop, yet a grid is.** The rule the shelf follows is
that a container holding controls takes no focus and paints no ring; this view is
not a container, it is the control; a reader has to be able to reach the works
with the keyboard (FR-BS-059). It therefore takes focus as the reader, the list in
the Bookmarks dialog and every other real control does.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QApplication, QListView, QMenu, QWidget

from voice_reader.domain.shelf.layout import DEFAULT_LAYOUT, ShelfLayout
from voice_reader.domain.shelf.progress import Progress
from voice_reader.domain.shelf.works import Work
from voice_reader.ui._message_box_utils import _in_tests

from voice_reader.ui.shelf_cover_loader import ShelfCoverLoader
from voice_reader.ui.shelf_model import ShelfModel
from voice_reader.ui.shelf_row import ROW_GAP, ShelfRowDelegate
from voice_reader.ui.shelf_tile import (
    TILE_GAP,
    TILE_HEIGHT,
    TILE_WIDTH,
    ShelfTileDelegate,
)

# Named after the work so a right click on the wrong tile is visible before
# it does anything.
# The modifiers Qt itself uses to extend a selection. A click holding one of
# them is gathering tiles, never asking for a book.
_GATHERING = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier

TAG_TEXT = "File {title} under a genre"
# Counted rather than named, since a list of nine titles is not a menu item
# anybody reads (FR-BS-046a).
TAG_MANY_TEXT = "File these {count} books under a genre"


class ShelfGrid(QListView):
    """Every work as a tile, drawn by the delegate, filled in the background."""

    work_activated = Signal(object)
    #: The reader asked to say what a work is (FR-BS-046).
    tag_requested = Signal(object)

    def __init__(
        self,
        *,
        covers=None,
        progress_of: Callable[[Work], Progress] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = ShelfCoverLoader(covers, parent=self) if covers else None
        self._delegate = ShelfTileDelegate(self)
        self._row_delegate = ShelfRowDelegate(self)
        self._layout = DEFAULT_LAYOUT
        self._model = ShelfModel(
            held_picture=covers.held_for if covers else _no_picture,
            progress_of=progress_of,
            want_picture=self._loader.want if self._loader else None,
            parent=self,
        )
        self.setModel(self._model)
        self._configure()
        self.set_layout(DEFAULT_LAYOUT)
        if self._loader is not None:
            # A bound method of a QObject living on this thread, so Qt queues
            # the call rather than running it on the worker that emitted it.
            self._loader.picture_ready.connect(self._model.picture_arrived)
        # One left click opens the work.  is deliberately not also
        # connected: a double click emits both, which would open the same book
        # twice and start a second load over the first.
        self.clicked.connect(self._on_activated)

    def _configure(self) -> None:
        """What holds in either layout; `set_layout` does what differs."""

        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        # Several at once, because filing 1251 works one at a time is not a
        # task anyone completes (FR-BS-046a). What it costs is that a click
        # now has to say which of the two things it means; see
        # `_on_activated`.
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setFrameShape(QListView.Shape.NoFrame)
        # Hover has to reach the delegate for a tile to ring under the pointer.
        self.setMouseTracking(True)
        # The tiles carry the shelf's surfaces; a viewport painting its own
        # would put a second background behind them.
        self.viewport().setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # What the controller says ---------------------------------------------

    def show_works(self, works: tuple[Work, ...]) -> None:
        self._model.set_works(works)

    def set_layout(self, layout: ShelfLayout) -> None:
        """FR-BS-051: tiles or rows, over the same works and the same model.

        One view in two modes rather than two views, so everything the shelf
        already does holds in both without being built twice: the ring and its
        lock, a click opening, Ctrl and Shift gathering, the right button
        filing, Enter opening, the covers arriving late.

        The view mode is set before the movement, because Qt resets the
        movement whenever the mode changes and a free movement would let a
        reader drag a tile out of its place.
        """

        self._layout = layout
        if layout is ShelfLayout.LIST:
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setWrapping(False)
            self.setSpacing(ROW_GAP)
            self.setGridSize(QSize())
            self.setItemDelegate(self._row_delegate)
        else:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setWrapping(True)
            self.setSpacing(TILE_GAP)
            self.setGridSize(QSize(TILE_WIDTH + TILE_GAP, TILE_HEIGHT + TILE_GAP))
            self.setItemDelegate(self._delegate)
        self.setMovement(QListView.Movement.Static)

    def shelf_layout(self) -> ShelfLayout:
        """The layout being drawn. Not `layout`, which Qt already means."""

        return self._layout

    def set_locked(self, locked: bool) -> None:
        """FR-BS-055a: no book can be opened, so every ring reads red.

        Both delegates are told, so switching layout while narrating cannot
        bring back a green ring. The viewport is repainted rather than left to
        the next hover, because the lock arrives while the pointer is already
        resting on a tile and that tile is exactly the one making the promise.
        """

        self._delegate.set_locked(locked)
        self._row_delegate.set_locked(locked)
        self.viewport().update()

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

    def selected_works(self) -> tuple[Work, ...]:
        """Every work gathered, in the order the shelf shows them.

        Walked over the model rather than over the selection, because the
        selection remembers the order they were clicked in and that is not the
        order anybody sees.
        """

        picked = {index.row() for index in self.selectedIndexes()}
        return tuple(
            work for row, work in enumerate(self._model.works()) if row in picked
        )

    def works_to_file(self, work: Work) -> tuple[Work, ...]:
        """The works a right click on `work` is about.

        The gathered ones where it was one of them, since that is plainly what
        the reader meant by gathering them; otherwise the single tile under the
        pointer, so a stale selection elsewhere cannot be filed by accident.
        """

        gathered = self.selected_works()
        return gathered if work in gathered and len(gathered) > 1 else (work,)

    def menu_for(self, works: tuple[Work, ...]) -> QMenu:
        """The menu offered over a tile, built but not shown.

        Built apart from being shown because showing it is modal: a suite that
        called it would stop there and wait for a press that never comes.
        """

        menu = QMenu(self)
        words = (
            TAG_TEXT.format(title=works[0].title)
            if len(works) == 1
            else TAG_MANY_TEXT.format(count=len(works))
        )
        action = menu.addAction(words)
        action.triggered.connect(lambda: self.tag_requested.emit(works))
        return menu

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """The right button over a tile offers to file what it is about."""

        work = self._model.work_at(self.indexAt(event.pos()))
        if work is None:
            super().contextMenuEvent(event)
            return
        menu = self.menu_for(self.works_to_file(work))
        if _in_tests():
            return
        menu.exec(event.globalPos())  # pragma: no cover (modal)

    def _on_activated(self, index) -> None:
        """A plain click opens the book; a modified one was gathering it."""

        if QApplication.keyboardModifiers() & _GATHERING:
            return
        work = self._model.work_at(index)
        if work is not None:
            self.work_activated.emit(work)


def _no_picture(_work: Work) -> bytes | None:
    """The answer where no cover service was wired: every tile a placeholder."""

    return None
