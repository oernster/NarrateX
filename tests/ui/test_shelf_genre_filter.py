"""Narrowing the shelf by genre.

FR-BS-042 to FR-BS-045. Real widgets against a real QApplication, with the
library standing in, because what is asserted is which works reach the grid.
"""

from __future__ import annotations

from voice_reader.domain.shelf.query import ShelfQuery
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow

from tests.ui._fakes_genres import ready, shown
from tests.ui._fakes_shelf import Controller

# Narrowing the shelf --------------------------------------------------------


def test_with_no_filter_the_whole_shelf_isshown(qapp) -> None:
    del qapp
    controller, _library = ready()

    shelf_helpers.refresh_shelf(controller)

    assert shown(controller) == ["Dracula", "Dune", "Untagged"]
    assert controller.window.shelf_view.lbl_count.text() == "3 works"


def test_a_ticked_genre_narrows_the_shelf_to_it(qapp) -> None:
    """FR-BS-042."""

    del qapp
    controller, _library = ready()

    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    assert shown(controller) == ["Dracula"]


def test_the_count_says_a_filter_is_narrowing_the_shelf(qapp) -> None:
    """A reader who forgot the filter is not left wondering where books went."""

    del qapp
    controller, _library = ready()

    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    assert controller.window.shelf_view.lbl_count.text() == "1 of 3 works"


def test_the_no_genre_choice_reaches_works_carrying_none(qapp) -> None:
    """FR-BS-044."""

    del qapp
    controller, _library = ready()

    shelf_helpers.apply_shelf_query(controller, ShelfQuery(include_ungenred=True))

    assert shown(controller) == ["Untagged"]


def test_clearing_the_filter_shows_everything_again(qapp) -> None:
    """FR-BS-045."""

    del qapp
    controller, _library = ready()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.apply_shelf_query(controller, ShelfQuery())

    assert shown(controller) == ["Dracula", "Dune", "Untagged"]
    assert controller.window.shelf_view.lbl_count.text() == "3 works"


def test_the_filter_is_remembered_across_a_refresh(qapp) -> None:
    del qapp
    controller, _library = ready()
    shelf_helpers.apply_shelf_query(
        controller, ShelfQuery(genres=frozenset({"Horror"}))
    )

    shelf_helpers.refresh_shelf(controller)

    assert shown(controller) == ["Dracula"]


def test_a_shelf_asked_for_nothing_yet_asks_for_everything(qapp) -> None:
    del qapp
    controller, _library = ready()

    assert shelf_helpers.shelf_query(controller) == ShelfQuery()


def test_a_controller_holding_rubbish_still_asks_for_everything(qapp) -> None:
    """Never lock a reader out of their shelf over a state read gone odd."""

    del qapp
    controller, _library = ready()
    controller._shelf_query = "not a query"  # noqa: SLF001

    assert shelf_helpers.shelf_query(controller) == ShelfQuery()


def test_opening_the_filter_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.filter_shelf(controller)


def test_the_filter_control_is_offered_only_once_there_is_a_shelf(qapp) -> None:
    del qapp
    controller, _library = ready()
    view = controller.window.shelf_view

    assert view.btn_filter.isEnabled() is False
    shelf_helpers.refresh_shelf(controller)
    assert view.btn_filter.isEnabled() is True


def test_the_filter_shuts_again_when_there_is_nothing_to_narrow(qapp) -> None:
    del qapp
    controller, _library = ready(works=())
    shelf_helpers.refresh_shelf(controller)

    assert controller.window.shelf_view.btn_filter.isEnabled() is False
