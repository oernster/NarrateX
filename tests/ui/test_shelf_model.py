"""The shelf model: what it answers; what it refuses to wait for.

Real widgets against a real QApplication; Qt is never mocked. The cover service
is a hand-written stand-in, because what is under test is how many times the
model asks it rather than what it answers.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QImage

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.progress import Progress, ReadingState
from voice_reader.domain.shelf.works import Work
from voice_reader.ui.shelf_model import (
    PIXMAP_CACHE_SIZE,
    TILE_ROLE,
    ShelfModel,
    TileData,
)


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


# The model ---------------------------------------------------------------


def test_the_model_counts_the_works_it_was_given(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: None)

    model.set_works((_work("Dune"), _work("Emma")))

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Dune"


def test_a_missing_picture_is_asked_for_once_and_not_waited_on(qapp) -> None:
    """FR-BS-038: a paint answers from the cache and asks for the rest."""

    del qapp
    asked: list[str] = []
    model = ShelfModel(
        held_picture=lambda _w: None, want_picture=lambda w: asked.append(w.token)
    )
    work = _work()
    model.set_works((work,))

    tile = model.data(model.index(0, 0), TILE_ROLE)

    assert isinstance(tile, TileData)
    assert tile.picture is None
    assert asked == [work.token]


def test_a_held_picture_is_decoded_and_kept(qapp) -> None:
    del qapp
    work = _work()
    reads = []

    def _held(asked_work):
        reads.append(asked_work.token)
        return _png()

    model = ShelfModel(held_picture=_held)
    model.set_works((work,))

    first = model.data(model.index(0, 0), TILE_ROLE)
    second = model.data(model.index(0, 0), TILE_ROLE)

    assert first.picture is not None
    assert second.picture is not None
    assert reads == [work.token], "the second paint must use the decoded copy"


def test_the_decoded_pictures_are_bounded(qapp) -> None:
    """FR-BS-037: what the grid holds does not grow with the collection."""

    del qapp
    works = tuple(_work(f"Book {number}") for number in range(PIXMAP_CACHE_SIZE + 25))
    model = ShelfModel(held_picture=lambda _w: _png(10, 15))
    model.set_works(works)

    for row in range(len(works)):
        model.data(model.index(row, 0), TILE_ROLE)

    assert len(model._pixmaps) == PIXMAP_CACHE_SIZE  # noqa: SLF001


def test_a_picture_arriving_redraws_that_row(qapp) -> None:
    del qapp
    work = _work()
    covers = _Covers()
    model = ShelfModel(held_picture=covers.held_for)
    model.set_works((_work("Emma"), work))
    changed: list[int] = []
    model.dataChanged.connect(lambda top, _bottom, _roles: changed.append(top.row()))

    covers.arrive(work)
    model.picture_arrived(work.token)

    assert changed == [1]


def test_a_picture_for_a_work_no_longer_shown_changes_nothing(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: None)
    model.set_works((_work("Emma"),))
    changed: list[int] = []
    model.dataChanged.connect(lambda top, _bottom, _roles: changed.append(top.row()))

    model.picture_arrived("someone|something else")

    assert changed == []


def test_progress_comes_from_the_library_when_one_is_wired(qapp) -> None:
    del qapp
    reading = Progress(state=ReadingState.READING, fraction=0.5)
    model = ShelfModel(held_picture=lambda _w: None, progress_of=lambda _w: reading)
    model.set_works((_work(),))

    tile = model.data(model.index(0, 0), TILE_ROLE)

    assert tile.progress is reading


def test_a_row_that_is_not_there_answers_nothing(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: None)
    model.set_works((_work(),))

    assert model.data(model.index(5, 0), TILE_ROLE) is None
    assert model.rowCount(model.index(0, 0)) == 0, "a work holds no rows of its own"


def test_the_tooltip_and_the_accessible_text_name_the_work(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: None)
    model.set_works((_work(), _work("Untitled", "")))

    assert "Frank Herbert" in model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
    assert (
        model.data(model.index(1, 0), Qt.ItemDataRole.AccessibleTextRole) == "Untitled"
    )
    assert model.data(model.index(1, 0), Qt.ItemDataRole.ToolTipRole) == "Untitled"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.EditRole) is None


def test_something_that_will_not_decode_leaves_the_tile_without_a_picture(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: b"not an image")
    model.set_works((_work(),))

    assert model.data(model.index(0, 0), TILE_ROLE).picture is None


def test_forgetting_the_pictures_empties_the_decoded_cache(qapp) -> None:
    del qapp
    model = ShelfModel(held_picture=lambda _w: _png())
    model.set_works((_work(),))
    model.data(model.index(0, 0), TILE_ROLE)

    model.forget_pictures()

    assert model._pixmaps == {}  # noqa: SLF001
