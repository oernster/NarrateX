"""FR-BS-055a: the shelf is the second door to an act that is already locked.

While the engine is narrating, the open control beside the shelf is disabled and
wears a red ring. These tests hold the shelf to the same rule: no work opens,
nothing belonging to the book being read aloud is cancelled, the reader keeps
their place and the refusal names what to do about it.
"""

from __future__ import annotations

from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_grid import ShelfGrid

from tests.ui._fakes_shelf import Controller, Engine, Library, Shelf, a_work


def _narrating_controller(window, shelf, status: NarrationStatus) -> Controller:
    controller = Controller(window, shelf)
    controller.narration_service = Engine(status)
    return controller


def test_a_narrating_engine_refuses_the_work_and_says_what_to_do(
    qapp, tmp_path, monkeypatch
) -> None:
    """FR-BS-055a: nothing loads, nothing is undone, the reader stays put."""

    del qapp
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"content")
    controller = _narrating_controller(
        MainWindow(), Shelf(Library(book)), NarrationStatus.PLAYING
    )
    controller.window.show_shelf_view()
    monkeypatch.setattr(
        shelf_helpers,
        "prepare_for_book_switch",
        lambda c: setattr(c, "prepared", c.prepared + 1),
    )
    monkeypatch.setattr(
        shelf_helpers,
        "load_selected_book",
        lambda c, *, path: c.loaded.append(path),
    )

    shelf_helpers.open_work(controller, a_work(root=tmp_path))

    assert controller.loaded == []
    # Nothing belonging to the book being read aloud was cancelled; the reader
    # was not thrown off the shelf to reach a load that never ran.
    assert controller.prepared == 0
    assert controller.window.showing_shelf()
    assert controller.window.lbl_status.text() == shelf_helpers.LOCKED_TEXT


def test_a_paused_engine_opens_the_same_work(qapp, tmp_path, monkeypatch) -> None:
    """FR-BS-055a: paused is not narrating, so the shelf acts as it always did."""

    del qapp
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"content")
    controller = _narrating_controller(
        MainWindow(), Shelf(Library(book)), NarrationStatus.PAUSED
    )
    monkeypatch.setattr(shelf_helpers, "prepare_for_book_switch", lambda c: None)
    monkeypatch.setattr(
        shelf_helpers,
        "load_selected_book",
        lambda c, *, path: c.loaded.append(path),
    )

    shelf_helpers.open_work(controller, a_work(root=tmp_path))

    assert controller.loaded == [book]


def test_the_shelf_lock_is_applied_when_the_shelf_is_opened(qapp, tmp_path) -> None:
    """A shelf shown between two state updates still draws itself truthfully."""

    del qapp
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"content")
    controller = _narrating_controller(
        MainWindow(),
        Shelf(Library(book, works=(a_work(root=tmp_path),))),
        NarrationStatus.PLAYING,
    )
    controller.window.shelf_view.install_grid(ShelfGrid())

    shelf_helpers.refresh_shelf(controller)

    assert controller.window.shelf_view.grid.itemDelegate()._locked is True


def test_the_shelf_lock_with_no_grid_installed_does_nothing(qapp) -> None:
    """A build whose shelf has no grid yet is not a failure to report."""

    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.apply_shelf_lock(controller, locked=True)
