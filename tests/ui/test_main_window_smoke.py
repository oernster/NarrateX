from __future__ import annotations

from voice_reader.ui.main_window import MainWindow
from voice_reader.version import APP_NAME


def test_main_window_highlight_smoke(qapp) -> None:
    del qapp
    w = MainWindow()
    w.set_reader_text("Hello\nWorld")
    w.highlight_range(0, 5)
    w.highlight_range(None, None)


def test_main_window_cover_smoke(qapp) -> None:
    del qapp
    w = MainWindow()
    w.set_cover_image(None)
    # Random bytes should be handled gracefully (no crash).
    w.set_cover_image(b"not-an-image")


def test_main_window_help_and_about_smoke(qapp) -> None:
    del qapp
    w = MainWindow()

    assert w.windowTitle() == APP_NAME
    assert hasattr(w, "btn_help")
    assert w.btn_help.toolTip(), "Expected a tooltip to indicate clickability"

    about = w.build_about_dialog()
    assert APP_NAME in about.windowTitle()
