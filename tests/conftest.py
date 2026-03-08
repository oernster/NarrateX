from __future__ import annotations

from pathlib import Path

import pytest


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for lightweight UI tests."""

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # Avoid Qt auto-quitting due to window lifetimes during tests.
    try:
        app.setQuitOnLastWindowClosed(False)
    except Exception:
        pass

    yield app

    # Best-effort: close windows before tearing down the application.
    _close_all_qt_windows(app)
    try:
        app.quit()
        app.processEvents()
    except Exception:
        pass


def _close_all_qt_windows(app) -> None:
    """Close and delete all Qt top-level widgets.

    Keeping widgets alive at interpreter shutdown can crash PySide6 on Windows
    (commonly manifested as 0xC0000409).
    """

    try:
        from PySide6.QtWidgets import QApplication

        windows = list(QApplication.topLevelWidgets())
    except Exception:
        windows = []

    for w in windows:
        try:
            w.close()
        except Exception:
            pass
        try:
            w.deleteLater()
        except Exception:
            pass

    try:
        app.processEvents()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _qt_cleanup_after_test(qapp):
    """Ensure each test leaves Qt with no orphaned windows."""

    yield
    _close_all_qt_windows(qapp)
