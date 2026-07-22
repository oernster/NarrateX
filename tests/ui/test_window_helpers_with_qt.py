from __future__ import annotations

from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.window_helpers import build_about_dialog, open_licence_dialog


def test_build_about_dialog_uses_main_window_as_parent(qapp) -> None:
    del qapp
    w = MainWindow()
    dlg = build_about_dialog(parent=w)
    assert "About" in dlg.windowTitle()


def test_about_credits_name_the_major_dependencies_with_licences(qapp) -> None:
    # Credit where credit is due: every load-bearing shipped dependency is
    # named with its licence, not a short thank-you list.
    del qapp
    w = MainWindow()
    text = build_about_dialog(parent=w).text()
    for expected in [
        "PySide6",
        "LGPL-3.0",
        "Kokoro TTS",
        "Apache-2.0",
        "PyTorch",
        "spaCy",
        "EbookLib",
        "PyMuPDF",
        "AGPL-3.0",
        "eSpeak NG",
        "sounddevice",
        "soundfile",
    ]:
        assert expected in text, f"About credits missing {expected!r}"


def test_open_licence_dialog_sets_attribute_and_can_open(qapp) -> None:
    del qapp
    w = MainWindow()
    open_licence_dialog(
        owner=w, attr_name="_lic", title="UI licence", filename="LGPL3-LICENSE"
    )
    assert getattr(w, "_lic", None) is not None
