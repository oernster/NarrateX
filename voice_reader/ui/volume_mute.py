"""The speaker button: mute and unmute, showing which one is in force.

Muted is not a second state beside the volume; it is the volume at zero. One
number is what the audio, the saved preference and the slider already share,
so there is nothing that can disagree with it. Pressing the speaker while sound
is on remembers the level and drops it to zero; pressing it again puts the
remembered level back. The picture follows the level wherever it came from, so
dragging the slider to zero shows the muted speaker too.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QSlider, QToolButton

from voice_reader.ui._icon_buttons import set_button_artwork
from voice_reader.ui.artwork import Artwork

MUTE_TEXT = "Mute (Up/Down adjusts the volume while focused)"
UNMUTE_TEXT = "Unmute (Up/Down adjusts the volume while focused)"


class VolumeMute(QObject):
    def __init__(
        self, *, button: QToolButton, slider: QSlider, unmute_level: int
    ) -> None:
        super().__init__(button)
        self._button = button
        self._slider = slider
        # The level unmuting returns to: the last audible one; the given
        # default when the volume has never been above zero.
        self._unmute_level = unmute_level
        slider.valueChanged.connect(self._on_level)
        button.clicked.connect(self.toggle)
        self._on_level(slider.value())

    def is_muted(self) -> bool:
        return self._slider.value() <= self._slider.minimum()

    def toggle(self) -> None:
        if self.is_muted():
            self._slider.setValue(self._unmute_level)
        else:
            self._slider.setValue(self._slider.minimum())

    def _on_level(self, value: int) -> None:
        if value > self._slider.minimum():
            self._unmute_level = int(value)
        muted = self.is_muted()
        words = UNMUTE_TEXT if muted else MUTE_TEXT
        set_button_artwork(
            self._button,
            Artwork.VOLUME_MUTED if muted else Artwork.VOLUME_CONTROL,
            words,
        )
        self._button.setToolTip(words)
        self._button.setAccessibleName(words)
