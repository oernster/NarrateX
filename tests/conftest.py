from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

# Ensure the project root is importable during pytest collection.
#
# Without this, imports like `import voice_reader` / `import installer.ops...` can
# resolve to unrelated site-packages (e.g. the PyPI `installer` package) when
# pytest's working directory / sys.path differs from a regular `python -c` run.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# Narration and synthesis threads, by the names they are started with.
_NARRATION_THREAD_PREFIXES = (
    "narration-thread",
    "tts-synth",
    "tts-kokoro",
    "tts-publisher",
    "tts-presynth",
)

# How long a stopped worker is given to notice. It re-checks the stop event
# every _QUEUE_PUT_TIMEOUT_SECONDS, so this is generous by an order of
# magnitude and still fails fast when a worker is genuinely wedged.
_THREAD_SHUTDOWN_GRACE_SECONDS = 2.0
_THREAD_POLL_SECONDS = 0.05


def _live_narration_threads() -> list[str]:
    return sorted(
        t.name
        for t in threading.enumerate()
        if t.is_alive() and t.name.startswith(_NARRATION_THREAD_PREFIXES)
    )


@pytest.fixture(autouse=True)
def no_leaked_narration_threads():
    """Fail the test that leaks a worker, rather than the one that trips over it.

    A synthesis worker that outlives its test is a daemon thread still touching
    a service whose test has torn down. Left alone it surfaces much later as an
    intermittent native crash in whichever UI test happens to be building a
    window at the time, which names the wrong test and reproduces about one run
    in ten. Asserting here converts that into a deterministic failure that
    names the test that actually leaked.
    """

    before = set(_live_narration_threads())

    yield

    deadline = time.monotonic() + _THREAD_SHUTDOWN_GRACE_SECONDS
    while True:
        leaked = [n for n in _live_narration_threads() if n not in before]
        if not leaked or time.monotonic() >= deadline:
            break
        time.sleep(_THREAD_POLL_SECONDS)

    assert not leaked, (
        "This test left narration worker threads running: "
        f"{', '.join(leaked)}.\n"
        "Stop the service (and wait for it) before the test returns. A worker "
        "blocked on a full queue used to be unstoppable; if one is wedged "
        "again, that is the defect rather than this assertion."
    )


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
