"""Tooltips show over a window that is not the active one.

Qt shows no tooltip over an inactive window unless that window carries
`WA_AlwaysShowToolTips`; that was measured on the real Windows platform,
because the offscreen platform does not model activation faithfully. What
this pins is the part that is ours: every top-level window, dialogs
included, is marked as it is shown; nothing else is.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

from voice_reader.ui import inactive_tooltips

ALWAYS_SHOW = Qt.WidgetAttribute.WA_AlwaysShowToolTips


@pytest.fixture
def installed(qapp: QApplication) -> Iterator[None]:
    inactive_tooltips.install(qapp)
    yield
    for child in qapp.children():
        if isinstance(child, inactive_tooltips._TooltipsOnInactiveWindows):
            qapp.removeEventFilter(child)
            child.deleteLater()


@pytest.mark.usefixtures("installed")
def test_every_window_is_marked_as_it_is_shown() -> None:
    window = QWidget()
    button = QPushButton("hover", window)
    dialog = QDialog(window)
    assert not window.testAttribute(ALWAYS_SHOW)

    window.show()
    dialog.show()

    assert window.testAttribute(ALWAYS_SHOW)
    assert dialog.testAttribute(ALWAYS_SHOW)
    assert not button.testAttribute(ALWAYS_SHOW)
    dialog.close()
    window.close()
