from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Installer UI is Windows-only")
def test_installer_licence_button_opens_dialog(qapp, monkeypatch) -> None:
    """Smoke test for the installer Licence button and dialog."""

    from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QPushButton

    # Avoid touching the real registry in tests.
    import installer.ui.main_window as mw

    monkeypatch.setattr(mw, "read_uninstall_entry", lambda _key: None)

    win = mw.InstallerMainWindow(SimpleNamespace(uninstall=False))
    win.show()
    qapp.processEvents()

    btn = win.findChild(QPushButton, "LicenceButton")
    assert btn is not None
    assert btn.text() == "Licence"
    assert btn.toolTip() == "Installer licence"

    btn.click()
    qapp.processEvents()

    dialogs = [
        w
        for w in QApplication.topLevelWidgets()
        if isinstance(w, QDialog) and w.windowTitle() == "Installer licence"
    ]
    assert dialogs, "Expected an Installer licence dialog to be open"

    dlg = dialogs[-1]

    editor = dlg.findChild(QPlainTextEdit, "LicenceText")
    assert editor is not None
    licence_text = editor.toPlainText()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in licence_text
    assert "Version 3, 29 June 2007" in licence_text

    dlg.close()
    qapp.processEvents()

