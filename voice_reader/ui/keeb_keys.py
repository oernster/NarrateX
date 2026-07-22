"""App-wide keyboard activation rules (the keeb model's Enter parity).

Qt only clicks a focused button on Space in a main window and routes Enter
to a dialog's default button instead of the focused control. The keeb model
wants the focused control to own its activation everywhere:

- Enter or Return clicks the focused enabled button (push, tool, check).
- A closed dropdown opens on Down, Enter or Return rather than silently
  changing value; an open popup keeps its native keys.
- The volume stop (the speaker button) owns Up and Down, adjusting the
  slider it is linked to via its `keeb_volume_slider` attribute.

One filter installed on the application covers the main window and every
dialog, so no surface can drift from the model.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox

# Percent moved per Up or Down press while the volume stop is focused.
_VOLUME_KEY_STEP = 5

_ACTIVATE_KEYS = (Qt.Key_Return, Qt.Key_Enter)


class KeebKeys(QObject):
    """Application event filter implementing the rules above.

    Stateless: everything is derived from the focused widget, so the filter
    holds no window references and survives any number of windows.
    """

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() != QEvent.KeyPress:
            return False

        focused = QApplication.focusWidget()
        # A key press is delivered to the focused widget first; reacting only
        # on that delivery keeps the filter from firing again as the event
        # propagates to parents.
        if focused is None or obj is not focused:
            return False

        key = event.key()

        if key in _ACTIVATE_KEYS:
            if isinstance(focused, QComboBox):
                if not focused.view().isVisible():
                    focused.showPopup()
                    return True
                return False
            if isinstance(focused, QAbstractButton) and focused.isEnabled():
                focused.click()
                return True
            return False

        if isinstance(focused, QComboBox) and key == Qt.Key_Down:
            if not focused.view().isVisible():
                focused.showPopup()
                return True
            return False

        if key in (Qt.Key_Up, Qt.Key_Down):
            slider = getattr(focused, "keeb_volume_slider", None)
            if slider is not None:
                step = _VOLUME_KEY_STEP if key == Qt.Key_Up else -_VOLUME_KEY_STEP
                slider.setValue(int(slider.value()) + step)
                return True

        return False


def install_keeb_keys() -> KeebKeys | None:
    """Install the filter on the application once; further calls reuse it."""

    app = QApplication.instance()
    if app is None:  # pragma: no cover (tests always run under a QApplication)
        return None

    existing = getattr(app, "_keeb_keys_filter", None)
    if isinstance(existing, KeebKeys):
        return existing

    keys = KeebKeys(app)
    app.installEventFilter(keys)
    app._keeb_keys_filter = keys  # noqa: SLF001 (idempotence anchor)
    return keys
