"""The voice picker's dropdown, wearing the select-voice artwork as its cue.

A plain QComboBox shows an item's icon only while that item is current, so its
placeholder (the resting state, since no voice is ever defaulted) could never
carry a picture. This paints the cue in front of whatever the combo shows.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QWidget,
)

from voice_reader.ui._icon_buttons import artwork_icon
from voice_reader.ui.artwork import ICON_PX, Artwork


class VoiceCombo(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cue = artwork_icon(Artwork.SELECT_VOICE)
        # The same drawn size as every other picture on the top row.
        self.setIconSize(QSize(ICON_PX, ICON_PX))

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        del event
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        if self.currentIndex() < 0:
            # What QComboBox itself does for a placeholder, repeated because
            # this override replaces its painting.
            option.currentText = self.placeholderText()
            option.palette.setBrush(
                QPalette.ColorRole.ButtonText,
                option.palette.placeholderText(),
            )
        option.currentIcon = self._cue
        option.iconSize = self.iconSize()
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)
