"""Dropdown gestures of the app-wide keeb key filter.

Opening on Down or Enter, committing on Space, committing-and-stepping on
Tab, and the real popup delivery shape (keyboard grab, focus on the combo).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox, QPushButton, QWidget

from voice_reader.ui.keeb_keys import KeebKeys


def _key_press(key) -> QKeyEvent:
    return QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)


def _focus(qapp, widget) -> None:
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    assert qapp.focusWidget() is widget


class TestDropdowns:
    def test_down_opens_a_closed_combo(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two"])
        host.show()
        _focus(qapp, combo)

        handled = KeebKeys().eventFilter(combo, _key_press(Qt.Key_Down))

        assert handled is True
        assert combo.view().isVisible()
        combo.hidePopup()
        host.close()

    def test_enter_opens_a_closed_combo(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two"])
        host.show()
        _focus(qapp, combo)

        handled = KeebKeys().eventFilter(combo, _key_press(Qt.Key_Return))

        assert handled is True
        assert combo.view().isVisible()
        combo.hidePopup()
        host.close()

    def test_keys_on_an_open_combo_are_left_to_the_popup(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two"])
        host.show()
        _focus(qapp, combo)
        combo.showPopup()
        # Opening the popup may move focus into it; put focus back on the
        # combo so the filter's already-open branches are the ones deciding.
        _focus(qapp, combo)
        assert combo.view().isVisible()

        keys = KeebKeys()
        assert keys.eventFilter(combo, _key_press(Qt.Key_Down)) is False
        assert keys.eventFilter(combo, _key_press(Qt.Key_Return)) is False
        combo.hidePopup()
        host.close()

    def test_space_on_a_closed_combo_stays_native(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two"])
        host.show()
        _focus(qapp, combo)

        assert KeebKeys().eventFilter(combo, _key_press(Qt.Key_Space)) is False
        host.close()

    def test_space_on_a_combo_with_open_popup_commits_the_highlight(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        host.show()
        _focus(qapp, combo)
        combo.showPopup()
        _focus(qapp, combo)
        combo.view().setCurrentIndex(combo.model().index(2, 0))

        handled = KeebKeys().eventFilter(combo, _key_press(Qt.Key_Space))

        assert handled is True
        assert combo.currentIndex() == 2
        assert not combo.view().isVisible()
        host.close()


class TestOpenPopup:
    def _open(self, qapp, host) -> QComboBox:
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        host.show()
        _focus(qapp, combo)
        combo.showPopup()
        view = combo.view()
        view.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        assert qapp.focusWidget() is view
        return combo

    def test_space_in_the_popup_commits_the_highlighted_item(self, qapp) -> None:
        host = QWidget()
        combo = self._open(qapp, host)
        combo.view().setCurrentIndex(combo.model().index(1, 0))

        handled = KeebKeys().eventFilter(combo.view(), _key_press(Qt.Key_Space))

        assert handled is True
        assert combo.currentIndex() == 1
        assert not combo.view().isVisible()
        host.close()

    def test_tab_in_the_popup_commits_and_steps_on(self, qapp) -> None:
        host = QWidget()
        combo = self._open(qapp, host)
        combo.view().setCurrentIndex(combo.model().index(2, 0))

        handled = KeebKeys().eventFilter(combo.view(), _key_press(Qt.Key_Tab))
        qapp.processEvents()

        assert handled is True
        assert combo.currentIndex() == 2
        assert not combo.view().isVisible()
        host.close()

    def test_backtab_in_the_popup_commits_and_steps_back(self, qapp) -> None:
        host = QWidget()
        combo = self._open(qapp, host)
        combo.view().setCurrentIndex(combo.model().index(1, 0))

        handled = KeebKeys().eventFilter(combo.view(), _key_press(Qt.Key_Backtab))
        qapp.processEvents()

        assert handled is True
        assert combo.currentIndex() == 1
        assert not combo.view().isVisible()
        host.close()

    def test_space_commits_even_when_focus_stayed_on_the_combo(self, qapp) -> None:
        # The real delivery shape: an open popup GRABS the keyboard without
        # taking focus, so the key event is addressed to the popup container
        # while the combo keeps focus. The filter must still commit.
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        host.show()
        _focus(qapp, combo)
        combo.showPopup()
        _focus(qapp, combo)
        combo.view().setCurrentIndex(combo.model().index(1, 0))
        container = combo.view().parentWidget()

        handled = KeebKeys().eventFilter(container, _key_press(Qt.Key_Space))

        assert handled is True
        assert combo.currentIndex() == 1
        assert not combo.view().isVisible()
        host.close()

    def test_space_addressed_to_the_viewport_also_commits(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one", "two", "three"])
        host.show()
        _focus(qapp, combo)
        combo.showPopup()
        _focus(qapp, combo)
        combo.view().setCurrentIndex(combo.model().index(2, 0))

        handled = KeebKeys().eventFilter(
            combo.view().viewport(), _key_press(Qt.Key_Space)
        )

        assert handled is True
        assert combo.currentIndex() == 2
        assert not combo.view().isVisible()
        host.close()

    def test_keys_on_an_unfocused_closed_combo_pass(self, qapp) -> None:
        host = QWidget()
        combo = QComboBox(host)
        combo.addItems(["one"])
        other = QPushButton("elsewhere", host)
        host.show()
        _focus(qapp, other)

        assert KeebKeys().eventFilter(combo, _key_press(Qt.Key_Down)) is False
        host.close()

    def test_other_popup_keys_stay_native(self, qapp) -> None:
        host = QWidget()
        combo = self._open(qapp, host)

        assert KeebKeys().eventFilter(combo.view(), _key_press(Qt.Key_Down)) is False
        combo.hidePopup()
        host.close()

    def test_a_popup_with_no_highlight_commits_nothing_but_closes(self, qapp) -> None:
        from PySide6.QtCore import QModelIndex

        host = QWidget()
        combo = self._open(qapp, host)
        combo.setCurrentIndex(0)
        combo.view().setCurrentIndex(QModelIndex())

        handled = KeebKeys().eventFilter(combo.view(), _key_press(Qt.Key_Space))

        assert handled is True
        assert combo.currentIndex() == 0
        assert not combo.view().isVisible()
        host.close()
