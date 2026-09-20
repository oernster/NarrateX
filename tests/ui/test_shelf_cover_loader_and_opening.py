"""The background cover reader; opening a work from a tile.

The loader is driven with a real thread and waited on, because what it promises
is that the read happens somewhere other than the thread that paints. Opening is
driven through the controller's own helper with the loader stubbed, so what is
asserted is which file was handed on and which view the reader ends up looking at.
"""

from __future__ import annotations

import threading
from pathlib import Path

from voice_reader.domain.shelf.works import Work
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_cover_loader import ShelfCoverLoader

from tests.ui._fakes_shelf import Controller, Library, Shelf, a_work


class _Covers:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.asked: list[str] = []
        self.threads: list[str] = []
        self.done = threading.Event()

    def thumbnail(self, work: Work) -> bytes | None:
        self.asked.append(work.token)
        self.threads.append(threading.current_thread().name)
        self.done.set()
        if self.error is not None:
            raise self.error
        return b"picture"


# The loader --------------------------------------------------------------


def test_a_wanted_picture_is_read_on_a_worker_and_announced(qapp) -> None:
    """The read happens off the Qt thread and the answer arrives back on it.

    The announcement is delivered through the event loop rather than on the
    worker, which is the whole point: a model touched from the worker would be
    touched while Qt was drawing from it. So the loop is pumped here, as the
    running application pumps it.
    """

    covers = _Covers()
    loader = ShelfCoverLoader(covers)
    announced: list[str] = []
    loader.picture_ready.connect(announced.append)
    work = a_work()

    loader.want(work)
    assert covers.done.wait(timeout=5.0)
    loader.stop()
    qapp.processEvents()

    assert covers.asked == [work.token]
    assert covers.threads == ["shelf-covers"]
    assert announced == [work.token]


def test_asking_twice_while_it_waits_reads_once(qapp) -> None:
    del qapp
    release = threading.Event()
    seen = threading.Event()

    class _Slow(_Covers):
        def thumbnail(self, work: Work):
            seen.set()
            release.wait(timeout=5.0)
            return super().thumbnail(work)

    covers = _Slow()
    loader = ShelfCoverLoader(covers)
    work = a_work()

    loader.want(work)
    assert seen.wait(timeout=5.0)
    loader.want(work)
    release.set()
    assert covers.done.wait(timeout=5.0)
    loader.stop()

    assert covers.asked == [work.token]


def test_a_read_that_explodes_is_still_announced(qapp) -> None:
    """The model must drop the request; otherwise the work is asked forever."""

    covers = _Covers(error=RuntimeError("the drive went away"))
    loader = ShelfCoverLoader(covers)
    announced: list[str] = []
    loader.picture_ready.connect(announced.append)
    work = a_work()

    loader.want(work)
    assert covers.done.wait(timeout=5.0)
    loader.stop()
    qapp.processEvents()

    assert announced == [work.token]


def test_a_loader_with_no_service_asks_nothing(qapp) -> None:
    del qapp
    loader = ShelfCoverLoader(None)

    loader.want(a_work())
    loader.stop()


def test_nothing_is_asked_for_after_it_is_stopped(qapp) -> None:
    del qapp
    covers = _Covers()
    loader = ShelfCoverLoader(covers)
    loader.stop()

    loader.want(a_work())

    assert covers.asked == []


def test_a_second_want_after_the_worker_ended_starts_another(qapp) -> None:
    """The worker leaves when the queue empties, so a later scroll restarts it."""

    del qapp
    covers = _Covers()
    loader = ShelfCoverLoader(covers)
    first = a_work("Dune - Frank Herbert.epub")
    loader.want(first)
    assert covers.done.wait(timeout=5.0)
    loader._thread.join(timeout=5.0)  # noqa: SLF001
    covers.done.clear()

    loader.want(a_work("Emma - Jane Austen.epub"))
    assert covers.done.wait(timeout=5.0)
    loader.stop()

    assert len(covers.asked) == 2


def test_a_second_work_wanted_while_the_worker_runs_joins_the_queue(qapp) -> None:
    """The worker is started once; the queue is what holds the rest."""

    release = threading.Event()
    first_seen = threading.Event()

    class _Slow(_Covers):
        def thumbnail(self, work: Work):
            if not first_seen.is_set():
                first_seen.set()
                release.wait(timeout=5.0)
            return super().thumbnail(work)

    covers = _Slow()
    loader = ShelfCoverLoader(covers)

    loader.want(a_work("Dune - Frank Herbert.epub"))
    assert first_seen.wait(timeout=5.0)
    loader.want(a_work("Emma - Jane Austen.epub"))
    release.set()
    loader._thread.join(timeout=5.0)  # noqa: SLF001
    loader.stop()
    qapp.processEvents()

    assert len(covers.asked) == 2
    assert set(covers.threads) == {"shelf-covers"}


# Opening a work ----------------------------------------------------------


def test_opening_a_work_loads_its_file_and_shows_the_reader(
    qapp, tmp_path, monkeypatch
) -> None:
    """FR-BS-055: the same load the file dialog performs."""

    del qapp
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"content")
    controller = Controller(MainWindow(), Shelf(Library(book)))
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

    assert controller.loaded == [book]
    assert controller.prepared == 1
    assert not controller.window.showing_shelf()


def test_a_missing_file_names_the_path_and_loads_nothing(
    qapp, tmp_path, monkeypatch
) -> None:
    """FR-BS-056."""

    del qapp
    gone = tmp_path / "Gone - Nobody.epub"
    controller = Controller(MainWindow(), Shelf(Library(gone)))
    monkeypatch.setattr(
        shelf_helpers,
        "load_selected_book",
        lambda c, *, path: c.loaded.append(path),
    )

    shelf_helpers.open_work(controller, a_work(root=tmp_path))

    assert controller.loaded == []
    assert str(gone) in controller.window.lbl_status.text()


def test_opening_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = Controller(MainWindow(), None)

    shelf_helpers.open_work(controller, a_work())

    assert controller.loaded == []


def test_the_folder_dialog_opens_in_the_downloads_folder(
    qapp, tmp_path, monkeypatch
) -> None:
    """Books arrive in the downloads folder, so the search starts there."""

    del qapp
    (tmp_path / "Downloads").mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    controller = Controller(MainWindow(), Shelf(Library(tmp_path)))
    shown: list[str] = []

    def _dialog(_parent, _title, start):
        shown.append(start)
        return ""

    monkeypatch.setattr(
        shelf_helpers.QFileDialog, "getExistingDirectory", staticmethod(_dialog)
    )

    shelf_helpers.choose_shelf_root(controller)

    assert shown == [str(tmp_path / "Downloads")]


def test_a_machine_with_no_downloads_folder_opens_at_home(
    qapp, tmp_path, monkeypatch
) -> None:
    del qapp
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert shelf_helpers._first_folder_to_show() == tmp_path  # noqa: SLF001
