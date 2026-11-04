from __future__ import annotations

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QLabel

from voice_reader.ui._help_dialogs import qt_source_links
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


def test_about_links_the_source_of_the_qt_and_pyside6_it_runs_on(qapp) -> None:
    # The LGPL-3.0 asks for the shipped Qt's source to be reachable; the links
    # name the running versions and the browser opens them from the dialog.
    # QMessageBox makes rich-text links clickable by default; this pins it.
    del qapp
    window = MainWindow()
    box = build_about_dialog(parent=window)

    text = box.text()
    assert f'qt5.git/tag/?h=v{qVersion()}"' in text
    assert f'pyside-setup.git/tag/?h=v{PySide6.__version__}"' in text
    label = next(
        child for child in box.findChildren(QLabel) if "qt5.git" in child.text()
    )
    assert label.openExternalLinks()
    assert label.textInteractionFlags() & Qt.LinksAccessibleByMouse


def test_qt_source_links_fill_both_versions() -> None:
    out = qt_source_links(qt_version="6.1.0", pyside_version="6.1.1")

    assert '<a href="https://code.qt.io/cgit/qt/qt5.git/tag/?h=v6.1.0">' in out
    assert "pyside-setup.git/tag/?h=v6.1.1" in out


def test_open_licence_dialog_sets_attribute_and_can_open(qapp) -> None:
    del qapp
    w = MainWindow()
    open_licence_dialog(
        owner=w, attr_name="_lic", title="UI licence", filename="LGPL3-LICENSE"
    )
    assert getattr(w, "_lic", None) is not None
