from __future__ import annotations

from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.window_helpers import build_about_dialog, open_licence_dialog


def test_build_about_dialog_uses_main_window_as_parent(qapp) -> None:
    del qapp
    w = MainWindow()
    dlg = build_about_dialog(parent=w)
    assert "About" in dlg.windowTitle()


def test_open_licence_dialog_sets_attribute_and_can_open(qapp) -> None:
    del qapp
    w = MainWindow()
    open_licence_dialog(
        owner=w, attr_name="_lic", title="UI licence", filename="LGPL3-LICENSE"
    )
    assert getattr(w, "_lic", None) is not None
