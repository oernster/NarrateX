from __future__ import annotations

import os

from PySide6.QtWidgets import QMessageBox

# Workaround for Windows packaged builds where the initial QMessageBox may be sized
# too narrowly, causing the title bar to truncate (e.g. "I…" instead of "Ideas").
#
# We "cheat" by adding an *invisible* informativeText consisting of NBSPs whose
# measured width roughly matches a sentence that we know produces a sensible
# dialog width in other Ideas flows.
_NO_BOOK_WIDTH_PAD_REF = "This runs in the background and won't interrupt playback."
# Use 2x the reference length to bias the layout toward a wider initial dialog,
# ensuring the title bar has enough horizontal room on Windows builds.
NO_BOOK_WIDTH_PAD = "\u00a0" * (len(_NO_BOOK_WIDTH_PAD_REF) * 2)


def _in_tests() -> bool:
    # pytest sets this environment variable for each test.
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _widen_message_box(box: QMessageBox, *, min_width: int) -> None:
    """Best-effort: make QMessageBox wide enough to avoid title truncation."""

    try:
        w = int(min_width)
    except Exception:  # pragma: no cover
        w = 420

    try:
        box.setMinimumWidth(w)
        box.adjustSize()
        box.resize(max(w, box.width()), box.height())
    except Exception:  # pragma: no cover
        pass


def open_nonblocking_message_box(
    box: QMessageBox,
    *,
    min_width: int,
    qtimer,
) -> None:
    """Open a non-blocking message box with a reliable width on Windows.

    In some environments, QMessageBox recalculates its final size at/after show.
    To avoid a very narrow initial window (which can truncate the title bar to
    e.g. "I…"), we widen both before and immediately after opening.

    `qtimer` is typically `PySide6.QtCore.QTimer` (or None / a stub).
    """

    _widen_message_box(box, min_width=min_width)
    if _in_tests():
        # Avoid using a QTimer in tests; it can make assertions racy.
        box.open()
        _widen_message_box(box, min_width=min_width)
        return

    box.open()
    try:
        # QTimer may be None in stripped environments; treat as best-effort.
        single_shot = getattr(qtimer, "singleShot", None)
        if callable(single_shot):
            single_shot(0, lambda: _widen_message_box(box, min_width=min_width))
    except Exception:  # pragma: no cover
        pass
