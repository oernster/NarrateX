"""The main window's controls rows: selection, transport and chapter nav.

Extracted from `_main_window_build` to keep both modules inside the 400-line
guardrail. Mutates `window` by attaching the control attributes tests and
controllers expect, then returns the two ready rows for the caller to place.

Every picture control comes from `_icon_buttons.icon_button`, so each one has
the same box, the same interaction ring and a tooltip saying what it does.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSlider

from voice_reader.ui._icon_buttons import icon_button
from voice_reader.ui._ui_controller_voices import VOICE_REGIONS, VOICE_SEXES
from voice_reader.ui.artwork import (
    ICON_BUTTON_PX,
    PRIMARY_BUTTON_PX,
    PRIMARY_ICON_PX,
    Artwork,
)
from voice_reader.ui.keeb_keys import install_keeb_keys
from voice_reader.ui.voice_combo import VoiceCombo

# Words for each picture control: its tooltip and its accessible text.
SELECT_BOOK_TEXT = "Select book"
REMOVE_BOOK_TEXT = "Remove current book (the file is kept)"
PLAY_TEXT = "Play"
PAUSE_TEXT = "Pause"
STOP_TEXT = "Stop"
VOLUME_TEXT = "Volume (Up/Down adjusts while focused)"
BOOKMARKS_TEXT = "Bookmarks"
SECTIONS_TEXT = "Sections"
PREVIOUS_CHAPTER_TEXT = "Previous chapter"
NEXT_CHAPTER_TEXT = "Next chapter"

SPEEDS = ("0.75x", "1.00x", "1.25x", "1.50x", "2.00x")
DEFAULT_SPEED = "1.00x"
# UX default: 25% until a persisted preference is loaded.
DEFAULT_VOLUME = 25
VOLUME_SLIDER_WIDTH = 140
VOICE_COMBO_MIN_WIDTH = 220
SPEED_COMBO_MIN_WIDTH = 95
ROW_SPACING = 8


def _text_button(window: Any, attr: str, *, artwork: Artwork, text: str, **kw):
    button = icon_button(artwork=artwork, text=text, tooltip=text, **kw)
    setattr(window, attr, button)
    return button


def build_controls_rows(window: Any, *, strings) -> tuple[QHBoxLayout, QHBoxLayout]:
    """Build the controls row and the chapter-nav row.

    Returns `(controls, chapter_nav)` for the caller to add to its panel.
    """

    controls = QHBoxLayout()
    controls.setSpacing(ROW_SPACING)

    _text_button(
        window, "btn_select_book", artwork=Artwork.SELECT_BOOK, text=SELECT_BOOK_TEXT
    )

    # Remove the current book from NarrateX's memory (bookmarks, resume,
    # ideas map, cached audio); the file on disk is never touched. Locked
    # until a book loads, like the picker.
    _text_button(
        window,
        "btn_remove_book",
        artwork=Artwork.REMOVE_CURRENT_BOOK,
        text=REMOVE_BOOK_TEXT,
    )
    window.btn_remove_book.setEnabled(False)

    window.voice_combo = VoiceCombo()
    window.voice_combo.setMinimumWidth(VOICE_COMBO_MIN_WIDTH)
    window.voice_combo.setMinimumHeight(ICON_BUTTON_PX)
    # No voice is defaulted: the combo rests on this placeholder until the
    # user chooses; the picker stays disabled until a book loads.
    window.voice_combo.setPlaceholderText(strings.select_voice)

    window.speed_combo = QComboBox()
    window.speed_combo.setMinimumWidth(SPEED_COMBO_MIN_WIDTH)
    window.speed_combo.setMinimumHeight(ICON_BUTTON_PX)
    for speed in SPEEDS:
        window.speed_combo.addItem(speed)
    window.speed_combo.setCurrentText(DEFAULT_SPEED)

    # Primary playback control: one larger Play/Pause toggle. Checkable so
    # narration state, not the click, decides what it shows.
    window.btn_play_pause = icon_button(
        artwork=Artwork.PLAY,
        text=PLAY_TEXT,
        tooltip=PLAY_TEXT,
        button_px=PRIMARY_BUTTON_PX,
        icon_px=PRIMARY_ICON_PX,
        object_name="playPauseButton",
    )
    window.btn_play_pause.setCheckable(True)

    _text_button(window, "btn_stop", artwork=Artwork.STOP, text=STOP_TEXT)
    window.btn_stop.setObjectName("stopButton")

    # Volume control (session-only, editable during playback).
    window.volume_slider = QSlider(Qt.Horizontal)
    window.volume_slider.setRange(0, 100)
    window.volume_slider.setValue(DEFAULT_VOLUME)
    window.volume_slider.setFixedWidth(VOLUME_SLIDER_WIDTH)
    window.volume_slider.setToolTip("Volume")
    # The volume STOP on the keyboard ring is the speaker button, never the
    # slider: the ring highlights the speaker and Up/Down adjust the level.
    window.volume_slider.setFocusPolicy(Qt.NoFocus)

    _text_button(
        window, "lbl_volume_icon", artwork=Artwork.VOLUME_CONTROL, text=VOLUME_TEXT
    )
    # The app-wide keeb filter reads this link to route Up/Down.
    window.lbl_volume_icon.keeb_volume_slider = window.volume_slider

    _text_button(
        window, "btn_bookmarks", artwork=Artwork.BOOKMARKS, text=BOOKMARKS_TEXT
    )
    window.btn_bookmarks.setProperty("bookmarkButton", True)
    _text_button(window, "btn_ideas", artwork=Artwork.SECTIONS, text=SECTIONS_TEXT)

    # Voice picker toggles: sex and region, filtering the dropdown. Their
    # artwork and tooltips are kept current by the controller's refresh.
    _, region_artwork, region_label = VOICE_REGIONS[0]
    _, sex_artwork, sex_label = VOICE_SEXES[0]
    _text_button(window, "btn_voice_sex", artwork=sex_artwork, text=sex_label)
    _text_button(window, "btn_voice_region", artwork=region_artwork, text=region_label)

    # Keeb key handling is app-wide now (Enter clicks the focused button,
    # Down/Enter open a closed dropdown, Up/Down drive the volume stop), so
    # every dialog inherits the same rules as the picker.
    install_keeb_keys()

    # Zone A: setup/content selection (left).
    zone_a = QHBoxLayout()
    zone_a.setSpacing(ROW_SPACING)
    zone_a.addWidget(window.btn_select_book)
    zone_a.addWidget(window.btn_remove_book)
    zone_a.addWidget(window.btn_voice_sex)
    zone_a.addWidget(window.btn_voice_region)
    zone_a.addWidget(window.voice_combo)
    zone_a.addWidget(QLabel("Speed"))
    zone_a.addWidget(window.speed_combo)

    # Zone B: primary playback (center)
    zone_b = QHBoxLayout()
    zone_b.setSpacing(ROW_SPACING)
    zone_b.addWidget(window.btn_play_pause)
    zone_b.addWidget(window.btn_stop)
    zone_b.addWidget(window.lbl_volume_icon)
    zone_b.addWidget(window.volume_slider)

    controls.addLayout(zone_a)
    controls.addStretch(1)
    controls.addLayout(zone_b)
    controls.addStretch(1)

    # Chapter navigation row: pictures only, the tooltip names the direction.
    chapter_nav = QHBoxLayout()
    chapter_nav.setSpacing(ROW_SPACING)
    _text_button(
        window,
        "btn_prev_chapter",
        artwork=Artwork.PREVIOUS_CHAPTER,
        text=PREVIOUS_CHAPTER_TEXT,
    )
    _text_button(
        window,
        "btn_next_chapter",
        artwork=Artwork.NEXT_CHAPTER,
        text=NEXT_CHAPTER_TEXT,
    )
    chapter_nav.addWidget(window.btn_prev_chapter)
    chapter_nav.addWidget(window.btn_next_chapter)
    chapter_nav.addStretch(1)

    return controls, chapter_nav
