"""App-wide keyboard activation rules (the keeb model's Enter parity).

Qt only clicks a focused button on Space in a main window, routes Enter to
a dialog's default button and leaves a dropdown's popup to commit only on
Enter. The keeb model wants the focused control to own its activation
everywhere:

- Enter or Return clicks the focused enabled button (push, tool, check).
- A closed dropdown opens on Down, Enter or Return rather than silently
  changing value.
- Inside an OPEN dropdown popup, Space commits the highlighted item, and
  Tab or Shift+Tab commits it AND steps to the next or previous stop, so
  choosing a voice and moving on is one gesture.
- The volume stop (the speaker button) owns all four arrows, adjusting
  the slider linked via its `keeb_volume_slider` attribute. NarrateX has
  no arrow-driven ring, so Left/Right are free to mean quieter/louder
  here, matching a horizontal slider.

Delivery detail that shapes the code: an open popup GRABS the keyboard
without taking focus, so its key events arrive addressed to the popup's
container or view while `QApplication.focusWidget()` still reports the
combo. Dropdown handling therefore keys off the RECEIVER's combo
ancestry; only the non-combo rules require the receiver to be the focused
widget.

One filter installed on the application covers the main window and every
dialog, so no surface can drift from the model.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox, QWidget

# Percent moved per arrow press while the volume stop is focused.
_VOLUME_KEY_STEP = 5

_ACTIVATE_KEYS = (Qt.Key_Return, Qt.Key_Enter)
_VOLUME_UP_KEYS = (Qt.Key_Up, Qt.Key_Right)
_VOLUME_DOWN_KEYS = (Qt.Key_Down, Qt.Key_Left)
_TAB_KEYS = (Qt.Key_Tab, Qt.Key_Backtab)


def _owning_combo(obj) -> QComboBox | None:
    """The combo `obj` belongs to: itself, or an ancestor of its popup."""

    widget = obj if isinstance(obj, QWidget) else None
    while widget is not None:
        if isinstance(widget, QComboBox):
            return widget
        widget = widget.parentWidget()
    return None


def _commit_highlight(combo: QComboBox) -> None:
    """Choose the popup's highlighted row, then close the popup."""

    row = int(combo.view().currentIndex().row())
    if row >= 0:
        combo.setCurrentIndex(row)
    combo.hidePopup()


class KeebKeys(QObject):
    """Application event filter implementing the rules above.

    Stateless: everything is derived from the receiving widget, so the
    filter holds no window references and survives any number of windows.
    """

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() != QEvent.KeyPress:
            return False

        key = event.key()

        combo = _owning_combo(obj)
        if combo is not None:
            if combo.view().isVisible():
                return self._popup_keys(combo, key, event)
            if obj is combo and QApplication.focusWidget() is combo:
                return self._closed_combo_keys(combo, key)
            return False

        focused = QApplication.focusWidget()
        # A key press is delivered to the focused widget first; reacting only
        # on that delivery keeps the filter from firing again as the event
        # propagates to parents.
        if focused is None or obj is not focused:
            return False

        if key in _ACTIVATE_KEYS:
            if isinstance(focused, QAbstractButton) and focused.isEnabled():
                focused.click()
                return True
            return False

        slider = getattr(focused, "keeb_volume_slider", None)
        if slider is not None:
            if key in _VOLUME_UP_KEYS:
                slider.setValue(int(slider.value()) + _VOLUME_KEY_STEP)
                return True
            if key in _VOLUME_DOWN_KEYS:
                slider.setValue(int(slider.value()) - _VOLUME_KEY_STEP)
                return True

        return False

    @staticmethod
    def _popup_keys(combo: QComboBox, key, event) -> bool:
        """Keys arriving anywhere in a combo with its popup open."""

        if key == Qt.Key_Space:
            _commit_highlight(combo)
            return True
        if key in _TAB_KEYS:
            _commit_highlight(combo)
            # Focus is back on the combo now; replay the Tab there so the
            # normal ring step happens after the commit.
            QApplication.postEvent(
                combo, QKeyEvent(QEvent.KeyPress, key, event.modifiers())
            )
            return True
        # Enter, Escape and the arrows keep their native popup meanings.
        return False

    @staticmethod
    def _closed_combo_keys(combo: QComboBox, key) -> bool:
        """Keys arriving on a focused combo whose popup is closed."""

        if key in _ACTIVATE_KEYS or key == Qt.Key_Down:
            combo.showPopup()
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
