"""The grid view: the works it shows, the keyboard, what it opens.

Real widgets against a real QApplication throughout.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QImage

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.shelf_grid import ShelfGrid
from voice_reader.ui.shelf_model import TILE_ROLE


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


# The grid ----------------------------------------------------------------


def test_the_grid_shows_the_works_it_is_given(qapp) -> None:
    del qapp
    grid = ShelfGrid(covers=_Covers())

    grid.show_works((_work("Dune"), _work("Emma")))

    assert len(grid.works()) == 2
    assert grid.model().rowCount() == 2
    grid.release()


def test_the_grid_takes_the_keyboard(qapp) -> None:
    """FR-BS-059: the works are reachable, so the grid is a real stop."""

    del qapp
    grid = ShelfGrid(covers=_Covers())

    assert grid.focusPolicy() & Qt.FocusPolicy.TabFocus
    grid.release()


def test_enter_opens_the_work_with_the_ring(qapp) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    del qapp
    grid = ShelfGrid(covers=_Covers())
    work = _work()
    grid.show_works((work,))
    grid.setCurrentIndex(grid.model().index(0, 0))
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    grid.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
    )

    assert opened == [work]
    grid.release()


def test_another_key_is_left_to_qt(qapp) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    del qapp
    grid = ShelfGrid(covers=_Covers())
    grid.show_works((_work(),))
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    grid.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
    )

    assert opened == []
    grid.release()


def test_enter_on_an_empty_shelf_opens_nothing(qapp) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    del qapp
    grid = ShelfGrid(covers=_Covers())
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    grid.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
    )

    assert opened == []
    grid.release()


def test_activating_a_tile_opens_that_work(qapp) -> None:
    del qapp
    grid = ShelfGrid(covers=_Covers())
    works = (_work("Dune"), _work("Emma"))
    grid.show_works(works)
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)

    grid.activated.emit(grid.model().index(1, 0))

    assert opened == [works[1]]
    grid.release()


def test_activating_a_row_that_is_gone_opens_nothing(qapp) -> None:
    del qapp
    grid = ShelfGrid(covers=_Covers())
    grid.show_works((_work(),))
    index = grid.model().index(0, 0)
    opened: list[Work] = []
    grid.work_activated.connect(opened.append)
    grid.show_works(())

    grid.activated.emit(index)

    assert opened == []
    grid.release()


def test_the_selected_work_is_the_one_under_the_ring(qapp) -> None:
    del qapp
    grid = ShelfGrid(covers=_Covers())
    works = (_work("Dune"), _work("Emma"))
    grid.show_works(works)

    assert grid.selected_work() is None
    grid.setCurrentIndex(grid.model().index(0, 0))
    grid.selectionModel().select(
        grid.model().index(0, 0), grid.selectionModel().SelectionFlag.Select
    )

    assert grid.selected_work() is works[0]
    grid.release()


def test_a_grid_with_no_cover_service_draws_placeholders(qapp) -> None:
    del qapp
    grid = ShelfGrid()

    grid.show_works((_work(),))

    assert grid.model().data(grid.model().index(0, 0), TILE_ROLE).picture is None
    grid.release()
