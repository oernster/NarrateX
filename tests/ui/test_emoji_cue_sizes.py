"""The emoji cues match the reference size (the 🧠 button at 16pt).

The book and mic emoji were locked to their captions' small font; they now
render as icon cues at the same point size as the top icon buttons, the
play/pause glyph is enlarged to visually match and the stop cue square is
sized to sit with them.
"""

from __future__ import annotations

from voice_reader.ui.main_window import MainWindow

# Keep in sync with _main_window_build's cue constants.
REFERENCE_POINT_SIZE = 16
TRANSPORT_GLYPH_POINT_SIZE = 18
STOP_CUE_PX = 20


def test_select_book_has_an_emoji_icon_cue(qapp) -> None:
    del qapp
    w = MainWindow()

    assert w.btn_select_book.text() == "Select Book"
    assert not w.btn_select_book.icon().isNull()
    # The icon must be at least the reference emoji's pixel footprint.
    assert w.btn_select_book.iconSize().height() >= REFERENCE_POINT_SIZE


def test_voice_emoji_is_a_reference_size_label(qapp) -> None:
    del qapp
    w = MainWindow()

    assert w.lbl_voice_icon.text() == "🎙"
    assert w.lbl_voice_icon.font().pointSize() == REFERENCE_POINT_SIZE
    # Same size as the brain button's emoji.
    assert w.lbl_voice_icon.font().pointSize() == w.btn_ideas.font().pointSize()


def test_transport_glyphs_are_enlarged(qapp) -> None:
    del qapp
    w = MainWindow()

    assert w.btn_play_pause.font().pointSize() == TRANSPORT_GLYPH_POINT_SIZE
    assert w.btn_stop.iconSize().height() == STOP_CUE_PX
