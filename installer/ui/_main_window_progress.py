"""Progress display for the installer's main window.

Two things go wrong easily here and both did. A worker reports progress from
another thread, so the values arrive as plain payloads that have to be read
defensively. And the bar shares a lifecycle with the buttons, so releasing the
controls at the end of an operation used to take the bar off screen before its
finished value had been shown.

Keeping both in one place makes that lifecycle explicit: the bar appears when
work starts, fills as the work reports, holds briefly at full, then retires.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow

# A finished operation fills the bar completely.
COMPLETE_PCT = 100

# How long the finished bar and its message stay on screen. Long enough to
# register as "that worked", short enough not to feel like a pause.
COMPLETE_LINGER_MS = 1200

_MIN_PCT = 0


def on_progress(window: InstallerMainWindow, payload) -> None:  # noqa: ANN001
    """Apply one progress report from the worker thread.

    A payload is either a plain message, or a mapping carrying a percentage
    alongside one. Anything else is ignored rather than trusted.
    """

    if isinstance(payload, dict):
        pct = payload.get("pct")
        msg = payload.get("message", "")
        if isinstance(pct, int):
            window._progress_bar.setValue(max(_MIN_PCT, min(COMPLETE_PCT, pct)))
        if msg:
            window._progress.setText(str(msg))
        return

    if isinstance(payload, str) and payload:
        window._progress.setText(payload)


def set_ui_busy(
    window: InstallerMainWindow,
    busy: bool,
    *,
    show_progress: bool | None = None,
) -> None:
    """Enable or disable the controls, and show or hide the progress bar.

    `show_progress` defaults to `busy`. Completion overrides it: a filled bar
    has to stay on screen long enough to be seen, and hiding it in the same
    breath as filling it is why the bar never reached 100%.
    """

    window._progress_bar.setVisible(busy if show_progress is None else show_progress)
    for w in [
        window._btn_primary_left,
        window._btn_primary_right,
        window._btn_uninstall,
        window._licence_btn,
        window._theme_toggle_btn,
        window._install_dir_edit,
        window._browse_btn,
        window._desktop_cb,
        window._startmenu_cb,
    ]:
        w.setEnabled(not busy)


def show_complete(window: InstallerMainWindow, *, message: str) -> None:
    """Fill the bar and name the outcome, leaving both on screen.

    Ordering matters. The controls are released only after the bar has been
    filled, and the bar is kept visible while that happens, so the finished
    state is something the user actually sees rather than a value written to a
    hidden widget.
    """

    window._progress_bar.setValue(COMPLETE_PCT)
    set_ui_busy(window, False, show_progress=True)
    window._progress.setText(message)


def clear_progress_display(window: InstallerMainWindow) -> None:
    """Retire the message and the bar together, once the pause has elapsed."""

    try:
        window._progress.setText("")
        window._progress_bar.setVisible(False)
    except Exception:
        pass
