"""Leaving nothing running at exit, proved with hand-written stand-ins.

No Qt here on purpose: the shutdown steps only ask their collaborators to stop,
so a plain object recording the asks is a truer test than a live widget tree.
"""

from __future__ import annotations

from voice_reader.ui import _ui_controller_shutdown as shutdown


class FakeDialog:
    def __init__(self, *, raises: bool = False) -> None:
        self.closed = False
        self._raises = raises

    def close(self) -> None:
        if self._raises:
            raise RuntimeError("already gone")
        self.closed = True


class FakeCancel:
    def __init__(self) -> None:
        self.set_called = False

    def set(self) -> None:
        self.set_called = True


class FakeTimer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class FakeManager:
    def __init__(self, *, raises: bool = False) -> None:
        self.cancelled: list[str] = []
        self._raises = raises

    def cancel(self, *, book_id: str) -> None:
        if self._raises:
            raise RuntimeError("worker gone")
        self.cancelled.append(book_id)


class FakeController:
    def __init__(self, **overrides: object) -> None:
        self._sections_dialog = None
        self._ideas_launch_cancel = None
        self._ideas_index_job_book_id = None
        self._ideas_index_timer = None
        self.idea_indexing_manager = None
        for name, value in overrides.items():
            setattr(self, name, value)


def test_the_sections_dialog_is_closed() -> None:
    dialog = FakeDialog()
    shutdown.close_sections_dialog(FakeController(_sections_dialog=dialog))
    assert dialog.closed


def test_a_dialog_that_refuses_to_close_does_not_stop_the_exit() -> None:
    controller = FakeController(_sections_dialog=FakeDialog(raises=True))
    shutdown.close_sections_dialog(controller)


def test_no_dialog_is_not_a_fault() -> None:
    shutdown.close_sections_dialog(FakeController())


def test_an_in_flight_launch_is_cancelled() -> None:
    cancel = FakeCancel()
    shutdown.cancel_ideas_launch(FakeController(_ideas_launch_cancel=cancel))
    assert cancel.set_called


def test_no_launch_in_flight_is_not_a_fault() -> None:
    shutdown.cancel_ideas_launch(FakeController())


def test_an_indexing_job_is_cancelled_and_its_timer_stopped() -> None:
    manager, timer = FakeManager(), FakeTimer()
    controller = FakeController(
        _ideas_index_job_book_id="abc",
        idea_indexing_manager=manager,
        _ideas_index_timer=timer,
    )
    shutdown.cancel_ideas_indexing(controller)
    assert manager.cancelled == ["abc"]
    assert timer.stopped
    assert controller._ideas_index_job_book_id is None  # noqa: SLF001


def test_no_indexing_job_means_nothing_to_cancel() -> None:
    manager = FakeManager()
    controller = FakeController(idea_indexing_manager=manager)
    shutdown.cancel_ideas_indexing(controller)
    assert manager.cancelled == []


def test_a_manager_that_raises_still_clears_the_job() -> None:
    controller = FakeController(
        _ideas_index_job_book_id="abc",
        idea_indexing_manager=FakeManager(raises=True),
    )
    shutdown.cancel_ideas_indexing(controller)
    assert controller._ideas_index_job_book_id is None  # noqa: SLF001


def test_a_job_with_no_manager_is_still_cleared() -> None:
    controller = FakeController(_ideas_index_job_book_id="abc")
    shutdown.cancel_ideas_indexing(controller)
    assert controller._ideas_index_job_book_id is None  # noqa: SLF001


def test_the_exit_runs_every_step() -> None:
    dialog, cancel, manager, timer = (
        FakeDialog(),
        FakeCancel(),
        FakeManager(),
        FakeTimer(),
    )
    controller = FakeController(
        _sections_dialog=dialog,
        _ideas_launch_cancel=cancel,
        _ideas_index_job_book_id="abc",
        idea_indexing_manager=manager,
        _ideas_index_timer=timer,
    )
    shutdown.on_app_exit(controller)
    assert dialog.closed
    assert cancel.set_called
    assert manager.cancelled == ["abc"]
    assert timer.stopped


def test_a_ui_callable_is_run() -> None:
    calls: list[int] = []
    shutdown.run_ui_callable(lambda: calls.append(1))
    assert calls == [1]


def test_something_that_is_not_callable_is_ignored() -> None:
    shutdown.run_ui_callable(object())


def test_a_ui_callable_that_raises_is_swallowed() -> None:
    def boom() -> None:
        raise RuntimeError("no")

    shutdown.run_ui_callable(boom)
