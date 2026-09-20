"""Choosing how the shelf is laid out (FR-BS-053 and FR-BS-053a).

The three orderings are the domain's and are tested there. What these ask is
whether the combo reaches them, whether an ordering chosen with nothing filtered
out is honoured at all and whether choosing one keeps the filter and the search
that were already on.

That middle question is the reason this file exists: the shelf used to ask the
library for an ordered view only when something was being filtered out, so an
ordering chosen on a whole shelf would have gone nowhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from voice_reader.application.services.shelf import ShelfLibrary
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.query import Order, ShelfQuery
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid
from voice_reader.ui.shelf_view import ORDERINGS

from tests.application.shelf.shelf_fakes import FakeBookmarks, FakeIndex, key, resume_at

ROOT = Path("H:/Books")


def entry(path, title, author, *, subjects=(), book_id=None, total=None) -> ShelfEntry:
    return ShelfEntry(
        key=key(path),
        title=title,
        author=author,
        subjects=tuple(subjects),
        book_id=book_id,
        total_chars=total,
    )


# Author order and title order disagree about these three, which is what makes
# them worth ordering: by author it is Clarke then King; by title alone the
# Clarke book with the later title falls between the two King ones.
RAMA = entry("H:/Books/a.mobi", "Rendezvous with Rama", "Arthur C. Clarke", book_id="r")
CARRIE = entry("H:/Books/b.mobi", "Carrie", "Stephen King", book_id="c")
SHINING = entry(
    "H:/Books/c.mobi", "The Shining", "Stephen King", subjects=("Horror",), book_id="s"
)

EVERY_BOOK = (RAMA, CARRIE, SHINING)

WHEN = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class _Covers:
    def held_for(self, work) -> bytes | None:
        del work
        return None

    def thumbnail(self, work) -> bytes | None:
        del work
        return None


class _Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.covers = _Covers()
        self.scanner = None
        self.thumbnails = None


class _Controller:
    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None


def _controller(entries=EVERY_BOOK, *, read=None):
    index = FakeIndex(roots=(ROOT,), entries=tuple(entries))
    shelf = _Shelf(ShelfLibrary(index=index, bookmarks=FakeBookmarks(read or {})))
    window = MainWindow()
    window.shelf_view.install_grid(ShelfGrid(covers=shelf.covers))
    return _Controller(window, shelf)


def _titles(controller) -> list[str]:
    return [work.title for work in controller.window.shelf_view.grid.works()]


def test_the_combo_offers_the_three_orderings(qapp) -> None:
    del qapp
    # The window is held rather than reached through: letting it go collects
    # the C++ side out from under the view still being read.
    window = MainWindow()
    view = window.shelf_view

    offered = [view.cmb_order.itemText(row) for row in range(view.cmb_order.count())]

    assert offered == [words for words, _rule in ORDERINGS]


def test_the_shelf_opens_in_author_then_title(qapp) -> None:
    """FR-BS-053, which is what the combo shows before anybody touches it."""

    del qapp
    controller = _controller()

    shelf_helpers.refresh_shelf(controller)

    assert _titles(controller) == ["Rendezvous with Rama", "Carrie", "The Shining"]
    assert controller.window.shelf_view.cmb_order.currentIndex() == 0
    controller.window.shelf_view.grid.release()


def test_title_alone_reorders_a_shelf_that_is_filtering_nothing(qapp) -> None:
    """The defect this file was written for: an ordering with no filter on."""

    del qapp
    controller = _controller()

    shelf_helpers.order_shelf(controller, Order.TITLE)

    assert _titles(controller) == ["Carrie", "Rendezvous with Rama", "The Shining"]
    controller.window.shelf_view.grid.release()


def test_most_recently_read_puts_the_last_book_first(qapp) -> None:
    """The acceptance in FR-BS-053a."""

    del qapp
    controller = _controller(
        read={
            "c": resume_at(10, when=WHEN),
            "s": resume_at(10, when=WHEN + timedelta(hours=1)),
        }
    )

    shelf_helpers.order_shelf(controller, Order.RECENTLY_READ)

    assert _titles(controller)[0] == "The Shining"
    controller.window.shelf_view.grid.release()


def test_a_book_never_opened_sorts_after_every_book_that_was(qapp) -> None:
    del qapp
    controller = _controller(read={"c": resume_at(10, when=WHEN)})

    shelf_helpers.order_shelf(controller, Order.RECENTLY_READ)

    assert _titles(controller)[0] == "Carrie"
    controller.window.shelf_view.grid.release()


def test_choosing_an_ordering_keeps_the_search(qapp) -> None:
    del qapp
    controller = _controller()
    shelf_helpers.search_shelf(controller, "king")

    shelf_helpers.order_shelf(controller, Order.TITLE)

    assert _titles(controller) == ["Carrie", "The Shining"]
    controller.window.shelf_view.grid.release()


def test_choosing_an_ordering_keeps_the_genre_filter(qapp) -> None:
    del qapp
    controller = _controller()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.order_shelf(controller, Order.TITLE)

    assert _titles(controller) == ["The Shining"]
    assert controller.window.shelf_view.lbl_count.text() == "1 of 3 works"
    controller.window.shelf_view.grid.release()


def test_the_combo_reaches_the_shelf(qapp) -> None:
    """The signal, not the helper: a combo wired to nothing would pass above."""

    del qapp
    controller = _controller()
    view = controller.window.shelf_view
    view.order_changed.connect(lambda rule: shelf_helpers.order_shelf(controller, rule))

    view.cmb_order.setCurrentIndex(1)

    assert _titles(controller) == ["Carrie", "Rendezvous with Rama", "The Shining"]
    view.grid.release()


def test_the_ordering_shuts_with_the_rest_while_a_scan_runs(qapp) -> None:
    del qapp
    window = MainWindow()
    view = window.shelf_view

    view.show_scanning()

    assert not view.cmb_order.isEnabled()


def test_the_ordering_opens_once_there_are_works(qapp) -> None:
    del qapp
    controller = _controller()

    shelf_helpers.refresh_shelf(controller)

    assert controller.window.shelf_view.cmb_order.isEnabled()
    controller.window.shelf_view.grid.release()
