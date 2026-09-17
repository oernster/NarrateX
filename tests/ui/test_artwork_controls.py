"""The artwork refresh: picture buttons, the picker cue, list rows and tooltips.

Every control that used to carry an emoji now shows shipped artwork, keeps its
purpose in a tooltip and falls back to words if its picture is missing.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QStyle

from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.ui import _icon_buttons
from voice_reader.ui._icon_buttons import ArtworkList, artwork_icon, icon_button
from voice_reader.ui.artwork import (
    ICON_BUTTON_PX,
    LIST_ROW_ICON_PX,
    TOP_ICON_BUTTON_PX,
    Artwork,
)
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.sentence_case_label import SentenceCaseLabel, sentence_case
from voice_reader.ui.voice_combo import VoiceCombo
from voice_reader.ui.window_helpers import TOOLTIP_WAKE_UP_MS

_PICTURE_CONTROLS = (
    "btn_select_book",
    "btn_remove_book",
    "btn_voice_sex",
    "btn_voice_region",
    "btn_play_pause",
    "btn_stop",
    "lbl_volume_icon",
    "btn_bookmarks",
    "btn_ideas",
    "btn_help",
    "btn_prev_chapter",
    "btn_next_chapter",
    "btn_ui_licence",
    "btn_backend_licence",
)


def test_every_artwork_name_loads(qapp) -> None:
    del qapp
    for name in Artwork:
        assert not artwork_icon(name).isNull(), name


def test_every_picture_control_shows_artwork_and_says_what_it_does(qapp) -> None:
    del qapp
    w = MainWindow()
    for attr in _PICTURE_CONTROLS:
        button = getattr(w, attr)
        assert not button.icon().isNull(), attr
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.toolTip(), attr
        assert button.property("iconButton") is True, attr
        # The words stay available to accessibility tooling.
        assert button.text(), attr


def test_select_book_and_chapter_nav_carry_no_visible_words(qapp) -> None:
    del qapp
    w = MainWindow()
    assert w.btn_select_book.toolTip() == "Select book"
    assert w.btn_prev_chapter.toolTip() == "Previous chapter"
    assert w.btn_next_chapter.toolTip() == "Next chapter"
    for button in (w.btn_select_book, w.btn_prev_chapter, w.btn_next_chapter):
        assert button.size() == QSize(TOP_ICON_BUTTON_PX, TOP_ICON_BUTTON_PX)


def test_play_pause_matches_its_neighbours_and_follows_state(qapp) -> None:
    del qapp
    w = MainWindow()
    for button in (w.btn_play_pause, w.btn_stop):
        assert button.size() == QSize(TOP_ICON_BUTTON_PX, TOP_ICON_BUTTON_PX)

    w.set_transport_playing(is_playing=True)
    assert w.btn_play_pause.toolTip() == "Pause"
    assert w.btn_play_pause.text() == "Pause"
    assert w.btn_play_pause.isChecked()

    w.set_transport_playing(is_playing=False)
    assert w.btn_play_pause.toolTip() == "Play"
    assert not w.btn_play_pause.isChecked()


def test_a_missing_picture_falls_back_to_words(qapp, tmp_path, monkeypatch) -> None:
    del qapp
    monkeypatch.setattr(
        _icon_buttons, "artwork_path", lambda name: tmp_path / f"{name}.png"
    )
    button = icon_button(artwork=Artwork.STOP, text="Stop", tooltip="Stop")
    assert button.icon().isNull()
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextOnly
    assert button.text() == "Stop"


def test_picture_buttons_ring_as_rounded_squares(qapp) -> None:
    del qapp
    sheet = MainWindow().styleSheet()
    assert 'QToolButton[iconButton="true"]:enabled:hover' in sheet
    assert 'QToolButton[iconButton="true"]:enabled:focus' in sheet
    # The circular rings (a radius of half the box) are gone.
    assert "border-radius: 26px" not in sheet
    assert "border-radius: 17px" not in sheet


def test_tooltips_open_promptly(qapp) -> None:
    del qapp
    w = MainWindow()
    hint = QStyle.StyleHint.SH_ToolTip_WakeUpDelay
    assert w.btn_help.style().styleHint(hint, None, w.btn_help) == TOOLTIP_WAKE_UP_MS
    # Every other hint still comes from the platform style.
    assert w.style().styleHint(QStyle.StyleHint.SH_ToolTip_FallAsleepDelay) > 0


def test_voice_combo_paints_its_cue_with_and_without_a_choice(qapp) -> None:
    del qapp
    combo = VoiceCombo()
    combo.setPlaceholderText("Select voice")
    combo.resize(220, ICON_BUTTON_PX)
    assert not combo.grab().isNull()

    combo.addItem("Emma (British Female)")
    combo.setCurrentIndex(0)
    assert not combo.grab().isNull()


def test_artwork_list_rows_wear_the_picture(qapp) -> None:
    del qapp
    rows = ArtworkList(Artwork.PIN)
    item = rows.add_row("  Chapter 1  ")
    assert rows.iconSize() == QSize(LIST_ROW_ICON_PX, LIST_ROW_ICON_PX)
    assert item.text() == "Chapter 1"
    assert not item.icon().isNull()
    assert rows.add_row(None).text() == ""


def test_status_line_always_opens_with_a_capital(qapp) -> None:
    del qapp
    assert sentence_case("idle") == "Idle"
    assert sentence_case("") == ""
    label = SentenceCaseLabel()
    label.setText(NarrationStatus.SYNTHESIZING.value)
    assert label.text() == "Synthesizing"

    w = MainWindow()
    assert isinstance(w.lbl_status, SentenceCaseLabel)
    w.lbl_status.setText(NarrationStatus.IDLE.value)
    assert w.lbl_status.text() == "Idle"


def test_progress_percentage_shares_the_count_line(qapp) -> None:
    """The bar's text is centred vertically, as the 0/0 label beside it is."""

    del qapp
    w = MainWindow()
    assert w.progress.alignment() & Qt.AlignmentFlag.AlignVCenter
    assert w.lbl_progress.alignment() & Qt.AlignmentFlag.AlignVCenter


def test_transport_row_is_centred_between_the_chapter_buttons(qapp) -> None:
    w = MainWindow()
    w.resize(1400, 700)
    w.show()
    qapp.processEvents()
    order = [w.btn_prev_chapter, w.btn_play_pause, w.btn_stop, w.btn_next_chapter]
    xs = [button.x() for button in order]
    assert xs == sorted(xs)
    assert all(button.y() == order[0].y() for button in order)
    # The row sits below the top controls rather than beside them.
    assert order[0].y() > w.btn_select_book.geometry().bottom()

    row = w.transport_row.geometry()
    space_left = order[0].geometry().left() - row.left()
    space_right = row.right() - order[-1].geometry().right()
    # Centred: the space either side differs by at most a rounding pixel.
    assert abs(space_left - space_right) <= 1
    w.close()
