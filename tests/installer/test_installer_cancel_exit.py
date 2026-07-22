"""Cancelling out of a running operation must not fake a failure.

Two defects sat behind the mid-install "Cancel && Exit" flow. A force-stopped
worker never emits its result, so the relay fabricated "Operation did not
return a result" and the finished callback raised a modal error over a window
that was already closing. And the progress bar only took layout space while
visible, so its appearance reflowed the fixed-height button rows into each
other on a window too short to hold them all.
"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace

import pytest

from installer.ui.worker import OperationController


class _Callbacks:
    """Records what the controller delivered to the UI."""

    def __init__(self) -> None:
        self.finished: list[object] = []
        self.progress: list[object] = []
        self.app_running: list[str] = []

    def start(self, controller: OperationController, fn) -> None:  # noqa: ANN001
        controller.start(
            fn,
            kwargs={},
            on_progress=self.progress.append,
            on_finished=self.finished.append,
            on_app_running=self.app_running.append,
        )


def _drain_until_stopped(qapp, controller: OperationController) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        qapp.processEvents()
        if not controller.is_running:
            break
    # Queued relay/finished events can land after the thread stops.
    for _ in range(10):
        qapp.processEvents()


class TestForceStopSuppressesTheFinishedCallback:
    def test_a_cancelled_operation_reports_nothing(self, qapp) -> None:
        # The defect: cancel-and-exit still delivered a failure result, which
        # the window turned into a modal error while closing.
        controller = OperationController()
        callbacks = _Callbacks()

        def _waits_for_cancel(*, cancel_event, progress) -> None:  # noqa: ANN001
            del progress
            cancel_event.wait(5.0)

        callbacks.start(controller, _waits_for_cancel)
        controller.force_stop(timeout_ms=3000)
        _drain_until_stopped(qapp, controller)

        assert callbacks.finished == []
        assert callbacks.app_running == []

    def test_a_normal_run_still_reports_its_result(self, qapp) -> None:
        # Pins the discrimination: suppression is scoped to force_stop, not a
        # blanket silencing of every finish.
        controller = OperationController()
        callbacks = _Callbacks()

        def _succeeds(*, cancel_event, progress) -> None:  # noqa: ANN001
            del cancel_event, progress

        callbacks.start(controller, _succeeds)
        _drain_until_stopped(qapp, controller)

        assert len(callbacks.finished) == 1
        assert callbacks.finished[0].ok is True

    def test_a_second_start_reports_again_after_a_force_stop(self, qapp) -> None:
        # Suppression must reset per operation, or one cancelled install would
        # mute every later one.
        controller = OperationController()
        callbacks = _Callbacks()

        def _waits_for_cancel(*, cancel_event, progress) -> None:  # noqa: ANN001
            del progress
            cancel_event.wait(5.0)

        def _succeeds(*, cancel_event, progress) -> None:  # noqa: ANN001
            del cancel_event, progress

        callbacks.start(controller, _waits_for_cancel)
        controller.force_stop(timeout_ms=3000)
        _drain_until_stopped(qapp, controller)

        callbacks.start(controller, _succeeds)
        _drain_until_stopped(qapp, controller)

        assert len(callbacks.finished) == 1
        assert callbacks.finished[0].ok is True


@pytest.mark.skipif(os.name != "nt", reason="Installer UI is Windows-only")
class TestTheBarKeepsItsSlot:
    @pytest.fixture()
    def window(self, qapp, monkeypatch):
        import installer.ui.main_window as mw

        monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: None)
        win = mw.InstallerMainWindow(SimpleNamespace(uninstall=False))
        win.show()
        qapp.processEvents()
        yield win
        win.close()

    def test_the_hidden_bar_still_reserves_layout_space(self, window) -> None:
        assert window._progress_bar.sizePolicy().retainSizeWhenHidden() is True

    def test_the_window_is_tall_enough_for_every_row(self, window, qapp) -> None:
        # The defect's precondition: a minimum height below the layout's
        # minimum is what let the rows collide at all.
        window._header_fit.ensure_now()
        qapp.processEvents()
        needed = window.centralWidget().minimumSizeHint().height()
        assert window.minimumHeight() >= needed

    def test_starting_work_moves_nothing(self, window, qapp) -> None:
        # The visible defect: Reinstall/Repair and Uninstall crushed into each
        # other the moment "Extracting payload..." appeared.
        window._header_fit.ensure_now()
        qapp.processEvents()
        root = window.centralWidget()
        buttons = [
            window._btn_primary_left,
            window._btn_primary_right,
            window._btn_uninstall,
        ]
        before = [b.mapTo(root, b.rect().topLeft()).y() for b in buttons]

        window._set_ui_busy(True)
        window._progress.setText("Extracting payload...")
        window._progress_bar.setValue(40)
        qapp.processEvents()

        after = [b.mapTo(root, b.rect().topLeft()).y() for b in buttons]
        assert after == before
