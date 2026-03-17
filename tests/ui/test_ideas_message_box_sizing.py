from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from voice_reader.ui.main_window import MainWindow


def test_open_message_box_uses_qtimer_to_rewiden_after_open(monkeypatch, qapp) -> None:
    """Cover the non-test runtime path that schedules a post-show widen.

    This is intended to prevent Windows title-bar truncation (e.g. "I…") when the
    initial QMessageBox size is computed too narrowly.
    """

    del qapp
    from voice_reader.ui import _message_box_utils

    # Force the runtime (non-test) branch.
    monkeypatch.setattr(_message_box_utils, "_in_tests", lambda: False)

    calls = SimpleNamespace(widen=0, opened=0, singleshot=0)

    def _widen_stub(box: QMessageBox, *, min_width: int) -> None:
        del box, min_width
        calls.widen += 1

    monkeypatch.setattr(_message_box_utils, "_widen_message_box", _widen_stub)

    # Avoid actually showing a native dialog in tests.
    box = QMessageBox(MainWindow())
    monkeypatch.setattr(box, "open", lambda: setattr(calls, "opened", calls.opened + 1))

    # Patch QTimer.singleShot so the callback runs immediately (deterministic).
    class _Timer:
        @staticmethod
        def singleShot(_ms: int, fn) -> None:  # noqa: N802
            calls.singleshot += 1
            fn()

    _message_box_utils.open_nonblocking_message_box(box, min_width=420, qtimer=_Timer)

    assert calls.opened == 1
    assert calls.singleshot == 1
    # Once before open, once after open.
    assert calls.widen >= 2
