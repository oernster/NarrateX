"""The shelf as a list; the list remembered (FR-BS-051 and FR-BS-052).

A real window, a real grid, a real delegate painting into a real image, so what
is read back is what a reader would see drawn. The preferences are a
hand-written stand-in holding one value, since the thing under test is that the
shelf asks and answers, not how a JSON file is written; that is tested beside
the repository itself.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QModelIndex, QRect
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QListView, QStyleOptionViewItem

from voice_reader.application.services.shelf import ShelfLibrary
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.layout import DEFAULT_LAYOUT, ShelfLayout
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui import _ui_controller_shelf_layout as layout_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_model import TILE_ROLE, TileData
from voice_reader.ui.shelf_row import (
    NO_GENRE_TEXT,
    ShelfRowDelegate,
    genre_words,
    row_height,
)
from voice_reader.ui.shelf_view import LAYOUT_TEXT

from tests.application.shelf.shelf_fakes import FakeBookmarks, FakeIndex, key

ROOT = Path("H:/Books")

SHINING = ShelfEntry(
    key=key("H:/Books/a.mobi"),
    title="The Shining",
    author="Stephen King",
    subjects=("Horror",),
)
RAMA = ShelfEntry(key=key("H:/Books/b.mobi"), title="Rama", author="Arthur C. Clarke")


class _Covers:
    def held_for(self, work) -> bytes | None:
        del work
        return None

    def thumbnail(self, work) -> bytes | None:
        del work
        return None


class _Preferences:
    """Holds one layout, counting the saves."""

    def __init__(self, layout: ShelfLayout | None = None) -> None:
        self.layout = layout
        self.saves = 0

    def load_shelf_layout(self) -> ShelfLayout | None:
        return self.layout

    def save_shelf_layout(self, layout: ShelfLayout) -> None:
        self.layout = layout
        self.saves += 1


class _Controller:
    """What the shelf helpers reach for, with the grid's own entry points."""

    def __init__(self, window, shelf, preferences=None) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None
        self.narration_service = SimpleNamespace(preferences_repo=preferences)

    def open_work(self, work) -> None:  # pragma: no cover (not clicked here)
        del work

    def tag_work(self, works) -> None:  # pragma: no cover (not clicked here)
        del works


def _controller(preferences=None) -> _Controller:
    index = FakeIndex(roots=(ROOT,), entries=(SHINING, RAMA))
    library = ShelfLibrary(index=index, bookmarks=FakeBookmarks())
    shelf = SimpleNamespace(
        library=library, covers=_Covers(), scanner=None, thumbnails=None
    )
    controller = _Controller(MainWindow(), shelf, preferences)
    shelf_helpers.install_shelf_grid(controller)
    return controller


# The layout itself ----------------------------------------------------------


def test_the_shelf_opens_as_a_grid_when_nothing_was_chosen(qapp) -> None:
    del qapp
    controller = _controller(_Preferences())

    grid = controller.window.shelf_view.grid
    assert grid.shelf_layout() is DEFAULT_LAYOUT is ShelfLayout.GRID
    assert grid.viewMode() is QListView.ViewMode.IconMode
    grid.release()


def test_the_shelf_opens_in_the_layout_last_used(qapp) -> None:
    """The acceptance in FR-BS-052."""

    del qapp
    controller = _controller(_Preferences(ShelfLayout.LIST))

    grid = controller.window.shelf_view.grid
    assert grid.shelf_layout() is ShelfLayout.LIST
    assert grid.viewMode() is QListView.ViewMode.ListMode
    grid.release()


def test_a_shelf_with_no_preferences_wired_still_opens(qapp) -> None:
    """Absence is an answer: nothing remembered is the default, not a fault."""

    del qapp
    controller = _controller(None)

    assert controller.window.shelf_view.grid.shelf_layout() is DEFAULT_LAYOUT
    controller.window.shelf_view.grid.release()


def test_the_button_switches_to_a_list_and_remembers_it(qapp) -> None:
    del qapp
    preferences = _Preferences()
    controller = _controller(preferences)

    layout_helpers.toggle_shelf_layout(controller)

    assert controller.window.shelf_view.grid.shelf_layout() is ShelfLayout.LIST
    assert preferences.layout is ShelfLayout.LIST
    assert preferences.saves == 1
    controller.window.shelf_view.grid.release()


def test_a_second_press_goes_back_to_the_grid(qapp) -> None:
    del qapp
    preferences = _Preferences()
    controller = _controller(preferences)

    layout_helpers.toggle_shelf_layout(controller)
    layout_helpers.toggle_shelf_layout(controller)

    grid = controller.window.shelf_view.grid
    assert grid.shelf_layout() is ShelfLayout.GRID
    assert grid.viewMode() is QListView.ViewMode.IconMode
    assert preferences.layout is ShelfLayout.GRID
    grid.release()


def test_switching_with_no_preferences_wired_switches_all_the_same(qapp) -> None:
    del qapp
    controller = _controller(None)

    layout_helpers.toggle_shelf_layout(controller)

    assert controller.window.shelf_view.grid.shelf_layout() is ShelfLayout.LIST
    controller.window.shelf_view.grid.release()


def test_switching_before_a_grid_exists_names_the_other_layout(qapp) -> None:
    """A view with no grid still keeps its button's words true."""

    del qapp
    window = MainWindow()
    controller = _Controller(window, None, _Preferences())

    layout_helpers.toggle_shelf_layout(controller)

    assert window.shelf_view.btn_layout.text() == LAYOUT_TEXT[ShelfLayout.GRID]


def test_the_button_names_what_a_press_does(qapp) -> None:
    del qapp
    controller = _controller(_Preferences())
    view = controller.window.shelf_view

    assert view.btn_layout.text() == LAYOUT_TEXT[ShelfLayout.LIST]
    layout_helpers.toggle_shelf_layout(controller)
    assert view.btn_layout.text() == LAYOUT_TEXT[ShelfLayout.GRID]
    view.grid.release()


def test_the_list_holds_the_same_works_as_the_grid(qapp) -> None:
    """One model under both, so switching loses and reorders nothing."""

    del qapp
    controller = _controller(_Preferences())
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    before = grid.works()

    layout_helpers.toggle_shelf_layout(controller)

    assert grid.works() == before
    grid.release()


def test_a_locked_shelf_stays_locked_in_the_list(qapp) -> None:
    """FR-BS-055a: switching layout mid-narration brings back no green ring."""

    del qapp
    controller = _controller(_Preferences())
    grid = controller.window.shelf_view.grid
    grid.set_locked(True)

    layout_helpers.toggle_shelf_layout(controller)

    assert grid.itemDelegate()._locked is True  # noqa: SLF001
    grid.release()


def test_the_layout_button_shuts_with_the_rest_while_a_scan_runs(qapp) -> None:
    del qapp
    window = MainWindow()

    window.shelf_view.show_scanning()

    assert not window.shelf_view.btn_layout.isEnabled()


# The row --------------------------------------------------------------------


def _paint_row(tile: TileData, *, width: int = 600) -> QImage:
    """Paint one row into an image and hand the image back."""

    delegate = ShelfRowDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, width, row_height(option))

    class _Index:
        def data(self, role):
            return tile if role == TILE_ROLE else None

    image = QImage(width, option.rect.height(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    delegate.paint(painter, option, _Index())
    painter.end()
    return image


def _tile(**changes) -> TileData:
    from voice_reader.domain.shelf.progress import UNREAD

    fields = {
        "title": "The Shining",
        "author": "Stephen King",
        "picture": None,
        "progress": UNREAD,
        "genres": ("Horror",),
    }
    fields.update(changes)
    return TileData(**fields)


def test_a_row_is_three_lines_tall_at_the_view_font(qapp) -> None:
    """Read off the fonts, so a larger font makes a taller row."""

    del qapp
    option = QStyleOptionViewItem()
    small = row_height(option)
    option.font.setPointSize(option.font.pointSize() * 2)

    assert row_height(option) > small


def test_a_row_asks_for_the_width_it_is_given(qapp) -> None:
    del qapp
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 640, 10)

    hint = ShelfRowDelegate().sizeHint(option, None)

    assert hint.width() == 640
    assert hint.height() == row_height(option)


def test_a_row_paints_something(qapp) -> None:
    del qapp
    image = _paint_row(_tile())

    painted = any(
        image.pixel(x, y) != 0
        for x in range(0, image.width(), 7)
        for y in range(image.height())
    )
    assert painted


def test_a_row_with_a_cover_paints_it(qapp) -> None:
    from PySide6.QtGui import QColor, QPixmap

    del qapp
    picture = QPixmap(20, 30)
    picture.fill(QColor("#ff0000"))

    image = _paint_row(_tile(picture=picture))

    reds = sum(
        1
        for x in range(image.width() // 4)
        for y in range(image.height())
        if QColor(image.pixel(x, y)).red() > 200
        and QColor(image.pixel(x, y)).green() < 60
    )
    assert reds > 0


def test_a_row_given_no_tile_falls_back_quietly(qapp) -> None:
    """A row the model cannot describe is left to Qt, not drawn as garbage."""

    del qapp
    delegate = ShelfRowDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 40)

    image = QImage(100, 40, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        # An index pointing at nothing: exactly what a model that cannot
        # describe the row answers with.
        delegate.paint(painter, option, QModelIndex())
    finally:
        painter.end()


def test_the_genres_read_as_one_line() -> None:
    assert genre_words(("Horror", "Thriller")) == "Horror, Thriller"


def test_a_work_with_no_genre_says_so() -> None:
    assert genre_words(()) == NO_GENRE_TEXT


def test_the_model_hands_a_row_its_genres(qapp) -> None:
    del qapp
    controller = _controller(_Preferences())
    shelf_helpers.refresh_shelf(controller)
    grid = controller.window.shelf_view.grid
    model = grid.model()

    tiles = [model.index(row, 0).data(TILE_ROLE) for row in range(model.rowCount())]

    shining = next(tile for tile in tiles if tile.title == "The Shining")
    assert "Horror" in shining.genres
    grid.release()
