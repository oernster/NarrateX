"""The speaker button mutes and unmutes; its picture follows the volume."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QSlider, QToolButton

from voice_reader.ui._icon_buttons import artwork_icon
from voice_reader.ui.artwork import ICON_PX, Artwork
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.volume_mute import MUTE_TEXT, UNMUTE_TEXT, VolumeMute

_DEFAULT_LEVEL = 25


def _shows(button: QToolButton, name: Artwork) -> bool:
    size = QSize(ICON_PX, ICON_PX)
    return (
        button.icon().pixmap(size).toImage()
        == artwork_icon(name).pixmap(size).toImage()
    )


def _mute(level: int) -> tuple[VolumeMute, QToolButton, QSlider]:
    button = QToolButton()
    slider = QSlider()
    slider.setRange(0, 100)
    slider.setValue(level)
    return (
        VolumeMute(button=button, slider=slider, unmute_level=_DEFAULT_LEVEL),
        button,
        slider,
    )


def test_pressing_the_speaker_mutes_then_restores_the_level(qapp) -> None:
    del qapp
    mute, button, slider = _mute(60)
    assert not mute.is_muted()
    assert button.toolTip() == MUTE_TEXT
    assert _shows(button, Artwork.VOLUME_CONTROL)

    button.click()
    assert slider.value() == 0
    assert mute.is_muted()
    assert button.toolTip() == UNMUTE_TEXT
    assert button.text() == UNMUTE_TEXT
    assert _shows(button, Artwork.VOLUME_MUTED)

    button.click()
    assert slider.value() == 60
    assert _shows(button, Artwork.VOLUME_CONTROL)


def test_dragging_to_zero_shows_muted_and_unmute_returns_the_last_level(
    qapp,
) -> None:
    del qapp
    mute, button, slider = _mute(40)
    slider.setValue(70)
    slider.setValue(0)
    assert _shows(button, Artwork.VOLUME_MUTED)
    mute.toggle()
    assert slider.value() == 70


def test_starting_silent_unmutes_to_the_default(qapp) -> None:
    del qapp
    mute, button, slider = _mute(0)
    assert mute.is_muted()
    assert _shows(button, Artwork.VOLUME_MUTED)
    button.click()
    assert slider.value() == _DEFAULT_LEVEL


def test_the_main_window_speaker_is_the_mute_toggle(qapp) -> None:
    del qapp
    w = MainWindow()
    level = w.volume_slider.value()
    w.lbl_volume_icon.click()
    assert w.volume_slider.value() == 0
    w.lbl_volume_icon.click()
    assert w.volume_slider.value() == level
