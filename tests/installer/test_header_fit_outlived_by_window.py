"""A header-fit pass still pending when its window is deleted must not run.

The controller is not a QObject, so a bare single-shot timer outlived the
window: measured, a pass firing after deletion raised on the dead window;
it ended the whole test process with an access violation when a main window
shared the application. The window is now the timers' context, so deleting it
cancels them.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.ui._dispose_testkit import dispose

# Longer than the controller's later pass, so both timers would have fired.
_OUTLAST_PASSES_MS = 100


def test_a_pass_pending_at_deletion_never_runs(qapp, monkeypatch) -> None:
    from PySide6.QtTest import QTest

    import installer.ui.main_window as mw

    del qapp
    monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: None)
    window = mw.InstallerMainWindow(SimpleNamespace(uninstall=False))
    window.show()
    ran: list[bool] = []
    controller = window._header_fit  # noqa: SLF001
    original = controller._ensure_fits  # noqa: SLF001
    controller._scheduled = False  # noqa: SLF001
    monkeypatch.setattr(
        type(controller), "_ensure_fits", lambda self: (ran.append(True), original())
    )
    controller.schedule()
    dispose(window)
    del window
    QTest.qWait(_OUTLAST_PASSES_MS)
    assert ran == []
