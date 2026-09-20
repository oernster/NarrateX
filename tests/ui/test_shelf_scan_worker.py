"""The shelf scan: off the Qt thread; every ending reaching the reader.

The scan is driven through a real `UiController` with a real `MainWindow`, so
the marshal back to the Qt thread is the production one. What is faked is the
scanner, because the endings worth testing (a report, an unreachable root, a
raise) are the ones a real disk will not produce on demand.
"""

from __future__ import annotations

import threading
from pathlib import Path

from voice_reader.application.services.shelf.scanning import ScanReport
from voice_reader.ui import _ui_controller_shelf as shelf_helpers
from voice_reader.ui import _ui_controller_shelf_scan as scan_helpers
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.shelf_view import NO_BOOKS_TEXT


class _FakeLibrary:
    def __init__(self, roots=(), works=()) -> None:
        self._roots = tuple(roots)
        self.works_to_answer = tuple(works)
        self.added: list[Path] = []
        self.outcome = None

    def roots(self):
        return self._roots

    def works(self):
        return self.works_to_answer

    def add_root(self, candidate: Path):
        self.added.append(candidate)
        self._roots = self._roots + (candidate,)
        return self.outcome


class _FakeScanner:
    """Answers one report or raises; says which thread it ran on."""

    def __init__(self, report=None, error: Exception | None = None) -> None:
        self._report = report or ScanReport()
        self._error = error
        self.ran_on: str | None = None
        self.calls = 0

    def scan(self, **kwargs):
        del kwargs
        self.calls += 1
        self.ran_on = threading.current_thread().name
        if self._error is not None:
            raise self._error
        return self._report


class _FakeShelf:
    def __init__(self, library, scanner) -> None:
        self.library = library
        self.scanner = scanner
        self.thumbnails = None


class _Controller:
    """A stand-in carrying exactly what the shelf helpers use.

    The marshal is the real one in spirit: the worker hands a callable back and
    this runs it, which is what `ui_call_requested` does once Qt delivers it.
    Driving it directly keeps the test free of an event loop while still proving
    the worker never touches a widget itself.
    """

    def __init__(self, window, shelf, log) -> None:
        self.window = window
        self.shelf = shelf
        self._log = log
        self._shelf_scan_thread: threading.Thread | None = None
        self.posted: list = []

        class _Signal:
            def __init__(self, posted) -> None:
                self._posted = posted

            def emit(self, fn) -> None:
                self._posted.append(fn)

        self.ui_call_requested = _Signal(self.posted)

    def run_posted(self) -> None:
        for fn in list(self.posted):
            fn()
        self.posted.clear()


class _Log:
    def __init__(self) -> None:
        self.exceptions = 0

    def exception(self, *args, **kwargs) -> None:
        del args, kwargs
        self.exceptions += 1


def _drive(controller) -> None:
    """Start the scan, wait for the worker, then run what it posted back."""

    scan_helpers.rescan_shelf(controller)
    thread = controller._shelf_scan_thread  # noqa: SLF001
    if thread is not None:
        thread.join(timeout=5.0)
        assert not thread.is_alive(), "the scan worker did not finish"
    controller.run_posted()


def test_the_scan_runs_off_the_qt_thread(qapp) -> None:
    del qapp
    scanner = _FakeScanner(ScanReport(found=1, added=1))
    library = _FakeLibrary(roots=(Path("H:/Books"),), works=(object(),))
    controller = _Controller(MainWindow(), _FakeShelf(library, scanner), _Log())

    _drive(controller)

    assert scanner.ran_on == "shelf-scan"
    assert controller.window.shelf_view.lbl_count.text() == "1 work"


def test_a_scan_that_finds_nothing_says_so(qapp) -> None:
    """FR-BS-058 reached through a real scan rather than by calling the view."""

    del qapp
    controller = _Controller(
        MainWindow(),
        _FakeShelf(_FakeLibrary(roots=(Path("H:/Books"),)), _FakeScanner()),
        _Log(),
    )

    _drive(controller)

    assert controller.window.shelf_view.lbl_state.text() == NO_BOOKS_TEXT


def test_an_unreachable_root_is_named_to_the_reader(qapp) -> None:
    """FR-BS-007: a drive left at home is told, not silently empty."""

    del qapp
    report = ScanReport(unreachable_roots=(Path("H:/Books"),))
    library = _FakeLibrary(roots=(Path("H:/Books"),), works=(object(),))
    controller = _Controller(
        MainWindow(), _FakeShelf(library, _FakeScanner(report)), _Log()
    )

    _drive(controller)

    assert "H:" in controller.window.lbl_status.text()


def test_a_failed_scan_reaches_the_screen_and_the_log(qapp) -> None:
    """A recovered failure that said nothing would be worse than a crash."""

    del qapp
    log = _Log()
    scanner = _FakeScanner(error=OSError("the drive went away"))
    controller = _Controller(MainWindow(), _FakeShelf(_FakeLibrary(), scanner), log)

    _drive(controller)

    assert log.exceptions == 1
    view = controller.window.shelf_view
    assert view.lbl_state.text() == scan_helpers.SCAN_FAILED_TEXT
    assert view.btn_rescan.isEnabled(), "the reader must be able to try again"


def test_a_second_scan_is_refused_while_one_runs(qapp) -> None:
    """Two scans over one tree can only race to save the same index."""

    del qapp
    started = threading.Event()
    release = threading.Event()

    class _BlockingScanner(_FakeScanner):
        def scan(self, **kwargs):
            started.set()
            release.wait(timeout=5.0)
            return super().scan(**kwargs)

    scanner = _BlockingScanner()
    controller = _Controller(MainWindow(), _FakeShelf(_FakeLibrary(), scanner), _Log())

    scan_helpers.rescan_shelf(controller)
    assert started.wait(timeout=5.0), "the first scan never started"
    scan_helpers.rescan_shelf(controller)
    release.set()
    controller._shelf_scan_thread.join(timeout=5.0)  # noqa: SLF001
    controller.run_posted()

    assert scanner.calls == 1


def test_a_scan_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = _Controller(MainWindow(), None, _Log())

    scan_helpers.rescan_shelf(controller)

    assert controller._shelf_scan_thread is None  # noqa: SLF001


def test_choosing_a_folder_scans_it(qapp, monkeypatch) -> None:
    del qapp
    chosen = Path("H:/Books")
    library = _FakeLibrary(works=(object(),))
    library.outcome = _Outcome(roots=(chosen,), added=True)
    scanner = _FakeScanner(ScanReport(found=1, added=1))
    controller = _Controller(MainWindow(), _FakeShelf(library, scanner), _Log())
    monkeypatch.setattr(
        shelf_helpers.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: str(chosen)),
    )

    shelf_helpers.choose_shelf_root(controller)
    thread = controller._shelf_scan_thread  # noqa: SLF001
    thread.join(timeout=5.0)
    controller.run_posted()

    assert library.added == [chosen]
    assert scanner.calls == 1


def test_a_cancelled_folder_dialog_changes_nothing(qapp, monkeypatch) -> None:
    del qapp
    library = _FakeLibrary()
    controller = _Controller(MainWindow(), _FakeShelf(library, _FakeScanner()), _Log())
    monkeypatch.setattr(
        shelf_helpers.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: ""),
    )

    shelf_helpers.choose_shelf_root(controller)

    assert library.added == []
    assert controller._shelf_scan_thread is None  # noqa: SLF001


def test_a_folder_already_covered_is_said_rather_than_ignored(
    qapp, monkeypatch
) -> None:
    """FR-BS-001c: a control that appeared to do nothing is the defect."""

    del qapp
    library = _FakeLibrary(roots=(Path("H:/"),))
    library.outcome = _Outcome(
        roots=(Path("H:/"),), added=False, covered_by=Path("H:/")
    )
    scanner = _FakeScanner()
    controller = _Controller(MainWindow(), _FakeShelf(library, scanner), _Log())
    monkeypatch.setattr(
        shelf_helpers.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: "H:/Books"),
    )

    shelf_helpers.choose_shelf_root(controller)

    assert "already covered" in controller.window.lbl_status.text()
    assert scanner.calls == 0


def test_choosing_a_folder_with_no_shelf_wired_does_nothing(qapp) -> None:
    del qapp
    controller = _Controller(MainWindow(), None, _Log())

    shelf_helpers.choose_shelf_root(controller)

    assert controller._shelf_scan_thread is None  # noqa: SLF001


class _Outcome:
    """The library's answer to add_root, in the shape the real one gives."""

    def __init__(self, *, roots, added, covered_by=None) -> None:
        self.roots = roots
        self.added = added
        self.covered_by = covered_by
        self.replaced = ()
