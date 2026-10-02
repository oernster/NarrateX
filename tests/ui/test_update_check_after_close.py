"""An update check whose window has gone before its answer comes back.

The check runs on a worker thread and hands its answer back by emitting a
signal on the controller, which is a child of the main window. If the window
is deleted while a check is out, the controller goes with it; the bare emit
then raised "Signal source has been deleted" on a thread nothing catches. No
path in the running application has been seen to delete the window that way
(quitting leaves it alive), so this is hardening rather than a reported fault.
Nobody is left to tell, so the answer is dropped; what must not happen is an
exception escaping a thread this application started.
"""

from __future__ import annotations

import threading

import shiboken6
from PySide6.QtWidgets import QWidget

from voice_reader.application.services.update_service import (
    UpdateService,
    platform_key_for,
)
from voice_reader.ui.update_check import UpdateCheckController

_CURRENT = "4.2.0"
# Far longer than a check against a stand-in takes, so only a hang reaches it.
_WAIT_SECONDS = 5


class _HeldSource:
    """A release source that answers only once the test lets it."""

    def __init__(self) -> None:
        self.asked = threading.Event()
        self.answer = threading.Event()
        self.worker: threading.Thread | None = None

    def latest_release(self):
        """Say it has been asked, then wait to be allowed to answer."""
        self.worker = threading.current_thread()
        self.asked.set()
        self.answer.wait(_WAIT_SECONDS)
        return None


class _Preferences:
    """No version has been skipped; nothing is ever written down."""

    def load_skipped_update_version(self) -> str | None:
        return None

    def save_skipped_update_version(self, version: str) -> None:
        raise AssertionError("an answer with nowhere to go saved a skip")


def test_an_answer_with_nowhere_to_go_is_dropped_not_raised(qapp, monkeypatch) -> None:
    escaped: list[BaseException | None] = []
    monkeypatch.setattr(
        threading, "excepthook", lambda raised: escaped.append(raised.exc_value)
    )
    source = _HeldSource()
    window = QWidget()
    controller = UpdateCheckController(
        UpdateService(
            source=source,
            current_version=_CURRENT,
            platform_key=platform_key_for("win32"),
        ),
        _Preferences(),
        window,
    )
    controller.check_manually()
    assert source.asked.wait(_WAIT_SECONDS), "the check never started"
    shiboken6.delete(window)
    assert not shiboken6.isValid(controller), "the window kept its controller"
    source.answer.set()
    source.worker.join(_WAIT_SECONDS)
    assert not source.worker.is_alive(), "the check never finished"
    assert escaped == []
