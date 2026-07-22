"""Tests for the app-wide keeb key filter.

Real widgets, real QApplication (offscreen); events are fed straight into
the filter so every rule is exercised deterministically.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox, QPushButton, QSlider, QToolButton, QWidget

from voice_reader.ui.keeb_keys import KeebKeys, install_keeb_keys


def _key_press(key, modifiers=Qt.NoModifier) -> QKeyEvent:
    return QKeyEvent(QEvent.KeyPress, key, modifiers)


def _focus(qapp, widget) -> None:
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    assert qapp.focusWidget() is widget


class TestInstall:
    def test_install_is_idempotent(self, qapp) -> None:
        first = install_keeb_keys()
        second = install_keeb_keys()

        assert isinstance(first, KeebKeys)
        assert second is first


class TestEnterActivates:
    def test_enter_clicks_the_focused_enabled_button(self, qapp) -> None:
        host = QWidget()
        button = QPushButton("Stop", host)
        clicks: list[bool] = []
        button.clicked.connect(lambda *_: clicks.append(True))
        host.show()
        _focus(qapp, button)

        handled = KeebKeys().eventFilter(button, _key_press(Qt.Key_Return))

        assert handled is True
        assert clicks == [True]
        host.close()

    def test_keypad_enter_clicks_a_tool_button(self, qapp) -> None:
        host = QWidget()
        button = QToolButton(host)
        clicks: list[bool] = []
        button.clicked.connect(lambda *_: clicks.append(True))
        host.show()
        _focus(qapp, button)

        handled = KeebKeys().eventFilter(button, _key_press(Qt.Key_Enter))

        assert handled is True
        assert clicks == [True]
        host.close()

    def test_enter_on_a_non_button_is_left_alone(self, qapp) -> None:
        host = QWidget()
        slider = QSlider(Qt.Horizontal, host)
        host.show()
        _focus(qapp, slider)

        assert KeebKeys().eventFilter(slider, _key_press(Qt.Key_Return)) is False
        host.close()

    def test_enter_on_a_plain_list_is_left_alone(self, qapp) -> None:
        # A bare list view is not a dropdown popup; its keys stay native.
        from PySide6.QtWidgets import QListWidget

        host = QWidget()
        lst = QListWidget(host)
        lst.addItems(["a", "b"])
        host.show()
        _focus(qapp, lst)

        assert KeebKeys().eventFilter(lst, _key_press(Qt.Key_Return)) is False
        host.close()

    def test_events_not_addressed_to_the_focus_widget_pass(self, qapp) -> None:
        host = QWidget()
        button = QPushButton("A", host)
        other = QPushButton("B", host)
        host.show()
        _focus(qapp, button)

        assert KeebKeys().eventFilter(other, _key_press(Qt.Key_Return)) is False
        host.close()

    def test_non_key_events_pass(self, qapp) -> None:
        host = QWidget()
        host.show()

        assert KeebKeys().eventFilter(host, QEvent(QEvent.FocusIn)) is False
        host.close()


class TestVolumeStop:
    def _volume_pair(self, host) -> tuple[QToolButton, QSlider]:
        slider = QSlider(Qt.Horizontal, host)
        slider.setRange(0, 100)
        slider.setValue(25)
        button = QToolButton(host)
        button.keeb_volume_slider = slider
        return button, slider

    def test_up_and_down_adjust_the_linked_slider(self, qapp) -> None:
        host = QWidget()
        button, slider = self._volume_pair(host)
        host.show()
        _focus(qapp, button)

        keys = KeebKeys()
        assert keys.eventFilter(button, _key_press(Qt.Key_Up)) is True
        assert slider.value() == 30
        assert keys.eventFilter(button, _key_press(Qt.Key_Down)) is True
        assert slider.value() == 25

    def test_horizontal_arrows_step_the_ring_not_the_volume(self, qapp) -> None:
        host = QWidget()
        button, slider = self._volume_pair(host)
        neighbour = QPushButton("next stop", host)
        host.show()
        _focus(qapp, button)

        handled = KeebKeys().eventFilter(button, _key_press(Qt.Key_Right))
        qapp.processEvents()

        assert handled is True
        assert slider.value() == 25
        assert qapp.focusWidget() is neighbour

    def test_the_slider_clamps_at_its_ends(self, qapp) -> None:
        host = QWidget()
        button, slider = self._volume_pair(host)
        slider.setValue(2)
        host.show()
        _focus(qapp, button)

        assert KeebKeys().eventFilter(button, _key_press(Qt.Key_Down)) is True
        assert slider.value() == 0

    def test_vertical_arrows_on_a_non_button_widget_pass(self, qapp) -> None:
        # A focusable widget that is neither a button nor volume-linked
        # keeps its native vertical arrows (a slider steps itself).
        host = QWidget()
        slider = QSlider(Qt.Horizontal, host)
        host.show()
        _focus(qapp, slider)

        assert KeebKeys().eventFilter(slider, _key_press(Qt.Key_Up)) is False
        host.close()


class TestRingArrows:
    def test_right_steps_forward_and_left_steps_back_on_buttons(self, qapp) -> None:
        host = QWidget()
        first = QPushButton("first", host)
        second = QPushButton("second", host)
        host.show()
        _focus(qapp, first)

        keys = KeebKeys()
        assert keys.eventFilter(first, _key_press(Qt.Key_Right)) is True
        qapp.processEvents()
        assert qapp.focusWidget() is second

        assert keys.eventFilter(second, _key_press(Qt.Key_Left)) is True
        qapp.processEvents()
        assert qapp.focusWidget() is first
        host.close()

    def test_horizontal_arrows_on_a_closed_combo_step_without_changing_value(
        self, qapp
    ) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        combo.setCurrentIndex(1)
        neighbour = QPushButton("next stop", host)
        host.show()
        _focus(qapp, combo)

        handled = KeebKeys().eventFilter(combo, _key_press(Qt.Key_Right))
        qapp.processEvents()

        assert handled is True
        assert combo.currentIndex() == 1
        assert qapp.focusWidget() is neighbour
        host.close()

    def test_horizontal_arrows_step_out_of_a_plain_list(self, qapp) -> None:
        from PySide6.QtWidgets import QListWidget

        host = QWidget()
        lst = QListWidget(host)
        lst.addItems(["a", "b"])
        neighbour = QPushButton("next stop", host)
        host.show()
        _focus(qapp, lst)

        handled = KeebKeys().eventFilter(lst, _key_press(Qt.Key_Right))
        qapp.processEvents()

        assert handled is True
        assert qapp.focusWidget() is neighbour
        host.close()

    def test_a_read_only_pane_rides_the_ring_horizontally(self, qapp) -> None:
        # The reader word-wraps, so Left/Right have no scroll to own; they
        # step the ring rather than trapping the cursor invisibly.
        from PySide6.QtWidgets import QTextEdit

        host = QWidget()
        pane = QTextEdit(host)
        pane.setPlainText("wrapped prose")
        pane.setReadOnly(True)
        pane.setTabChangesFocus(True)
        neighbour = QPushButton("next stop", host)
        host.show()
        _focus(qapp, pane)

        handled = KeebKeys().eventFilter(pane, _key_press(Qt.Key_Right))
        qapp.processEvents()

        assert handled is True
        assert qapp.focusWidget() is neighbour
        host.close()

    def test_an_editable_pane_keeps_its_caret_arrows(self, qapp) -> None:
        from PySide6.QtWidgets import QTextEdit

        host = QWidget()
        pane = QTextEdit(host)
        pane.setPlainText("editable prose")
        host.show()
        _focus(qapp, pane)

        assert KeebKeys().eventFilter(pane, _key_press(Qt.Key_Right)) is False
        host.close()

    def test_a_modified_arrow_keeps_its_native_meaning(self, qapp) -> None:
        # Shift+Right selects text in the reader; it must never ring-step.
        from PySide6.QtWidgets import QTextEdit

        host = QWidget()
        pane = QTextEdit(host)
        pane.setPlainText("selectable prose")
        pane.setReadOnly(True)
        host.show()
        _focus(qapp, pane)

        handled = KeebKeys().eventFilter(
            pane, _key_press(Qt.Key_Right, Qt.ShiftModifier)
        )

        assert handled is False
        host.close()

    def test_vertical_arrows_on_a_button_are_consumed_not_wandering(self, qapp) -> None:
        # Qt's default arrow navigation would hop focus geometrically,
        # losing the ring; a plain button stop has no vertical cursor.
        host = QWidget()
        first = QPushButton("first", host)
        QPushButton("below", host)
        host.show()
        _focus(qapp, first)

        keys = KeebKeys()
        assert keys.eventFilter(first, _key_press(Qt.Key_Down)) is True
        assert keys.eventFilter(first, _key_press(Qt.Key_Up)) is True
        qapp.processEvents()
        assert qapp.focusWidget() is first
        host.close()

    def test_up_on_a_closed_combo_is_consumed_without_changing_value(
        self, qapp
    ) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        combo.setCurrentIndex(1)
        host.show()
        _focus(qapp, combo)

        handled = KeebKeys().eventFilter(combo, _key_press(Qt.Key_Up))

        assert handled is True
        assert combo.currentIndex() == 1
        host.close()
