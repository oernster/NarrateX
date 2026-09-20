"""The background cover reader; opening a work from a tile.

The loader is driven with a real thread and waited on, because what it promises
is that the read happens somewhere other than the thread that paints. Opening is
driven through the controller's own helper with the loader stubbed, so what is
asserted is which file was handed on and which view the reader ends up looking at.
"""

from __future__ import annotations

import threading
from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.works import Work
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_cover_loader import ShelfCoverLoader


def _work(name: str = "Dune - Frank Herbert.epub", *, root: Path | None = None) -> Work:
    """A work named by its file, so two files are two works.

    The title and the author are read off the stem rather than fixed: a work is
    keyed on those, so a helper that hardcoded them would hand back the same work
    under two filenames and quietly defeat any test about two of them.
    """

    path = (root or Path("H:/Books")) / name
    title, _, author = path.stem.partition(" - ")
    key = ShelfKey(path=path, size_bytes=1, modified_ns=1)
    entry = ShelfEntry(key=key, title=title, author=author)
    return Work(title=title, author=author, entries=(entry,))


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
    work = _work()

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
    work = _work()

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
    work = _work()

    loader.want(work)
    assert covers.done.wait(timeout=5.0)
    loader.stop()
    qapp.processEvents()

    assert announced == [work.token]


def test_a_loader_with_no_service_asks_nothing(qapp) -> None:
    del qapp
    loader = ShelfCoverLoader(None)

    loader.want(_work())
    loader.stop()


def test_nothing_is_asked_for_after_it_is_stopped(qapp) -> None:
    del qapp
    covers = _Covers()
    loader = ShelfCoverLoader(covers)
    loader.stop()

    loader.want(_work())

    assert covers.asked == []


def test_a_second_want_after_the_worker_ended_starts_another(qapp) -> None:
    """The worker leaves when the queue empties, so a later scroll restarts it."""

    del qapp
    covers = _Covers()
    loader = ShelfCoverLoader(covers)
    first = _work("Dune - Frank Herbert.epub")
    loader.want(first)
    assert covers.done.wait(timeout=5.0)
    loader._thread.join(timeout=5.0)  # noqa: SLF001
    covers.done.clear()

    loader.want(_work("Emma - Jane Austen.epub"))
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

    loader.want(_work("Dune - Frank Herbert.epub"))
    assert first_seen.wait(timeout=5.0)
    loader.want(_work("Emma - Jane Austen.epub"))
    release.set()
    loader._thread.join(timeout=5.0)  # noqa: SLF001
    loader.stop()
    qapp.processEvents()

    assert len(covers.asked) == 2
    assert set(covers.threads) == {"shelf-covers"}


# Opening a work ----------------------------------------------------------


class _Library:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.recorded: list[tuple[str, int]] = []

    def path_to_open(self, work: Work) -> Path:
        return self._path


class _Shelf:
    def __init__(self, library) -> None:
        self.library = library
        self.scanner = None
        self.covers = None
        self.thumbnails = None


class _Controller:
    def __init__(self, window, shelf) -> None:
        self.window = window
        self.shelf = shelf
        self._shelf_scan_thread = None
        self.prepared = 0
        self.loaded: list[Path] = []


class _Log:
    def exception(self, *args, **kwargs) -> None:
        del args, kwargs


def test_opening_a_work_loads_its_file_and_shows_the_reader(
    qapp, tmp_path, monkeypatch
) -> None:
    """FR-BS-055: the same load the file dialog performs."""

    del qapp
    book = tmp_path / "Dune - Frank Herbert.epub"
    book.write_bytes(b"content")
    controller = _Controller(MainWindow(), _Shelf(_Library(book)))
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

    shelf_helpers.open_work(controller, _work(root=tmp_path))

    assert controller.loaded == [book]
    assert controller.prepared == 1
    assert not controller.window.showing_shelf()


def test_a_missing_file_names_the_path_and_loads_nothing(
    qapp, tmp_path, monkeypatch
) -> None:
    """FR-BS-056."""

    del qapp
    gone = tmp_path / "Gone - Nobody.epub"
    controller = _Controller(MainWindow(), _Shelf(_Library(gone)))
    monkeypatch.setattr(
        shelf_helpers,
        "load_selected_book",
        lambda c, *, path: c.loaded.append(path),
    )

    shelf_helpers.open_work(controller, _work(root=tmp_path))

    assert controller.loaded == []
    assert str(gone) in controller.window.lbl_status.text()


def test_opening_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = _Controller(MainWindow(), None)

    shelf_helpers.open_work(controller, _work())

    assert controller.loaded == []
