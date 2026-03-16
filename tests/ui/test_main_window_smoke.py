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

    # Exercise the about dialog show path (doesn't need to be visible).
    w.show_about_dialog()


def test_main_window_sections_button_exists(qapp) -> None:
    del qapp
    w = MainWindow()
    assert hasattr(w, "btn_ideas")
    assert w.btn_ideas.toolTip() == "Sections"
    assert not hasattr(w, "btn_search")


def test_sections_dialog_placeholder_smoke(qapp) -> None:
    """Sections dialog should show a non-blocking message box when no book is loaded."""

    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication, QMessageBox

    from voice_reader.ui._ui_controller_sections import open_structural_bookmarks_dialog

    w = MainWindow()
    w.show()
    qapp.processEvents()

    open_structural_bookmarks_dialog(
        SimpleNamespace(
            window=w,
            narration_service=SimpleNamespace(loaded_book_id=lambda: None),
            structural_bookmark_service=None,
        )
    )
    qapp.processEvents()

    boxes = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QMessageBox) and dlg.windowTitle() == "Sections"
    ]
    assert boxes, "Expected a Sections placeholder message box to be open"
    boxes[-1].close()
    qapp.processEvents()


def test_main_window_speed_combo_smoke(qapp) -> None:
    del qapp
    w = MainWindow()
    assert hasattr(w, "speed_combo")
    assert w.speed_combo.currentText() == "1.00x"


def test_main_window_volume_controls_smoke(qapp) -> None:
    del qapp
    w = MainWindow()
    assert hasattr(w, "volume_slider")
    assert w.volume_slider.minimum() == 0
    assert w.volume_slider.maximum() == 100
    assert w.volume_slider.value() == 100

    assert hasattr(w, "lbl_volume_icon")
    assert w.lbl_volume_icon.text() in {"🔊", "🔉", "🔇"}


def test_main_window_licence_buttons_open_dialogs(qapp) -> None:
    """Smoke test for the two top-right licence buttons."""

    from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QToolButton

    w = MainWindow()
    w.show()
    qapp.processEvents()

    btn_ui = w.findChild(QToolButton, "uiLicenceButton")
    assert btn_ui is not None
    assert btn_ui.toolTip() == "UI licence"

    btn_backend = w.findChild(QToolButton, "backendLicenceButton")
    assert btn_backend is not None
    assert btn_backend.toolTip() == "Backend licence"

    btn_ui.click()
    qapp.processEvents()

    ui_dialogs = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QDialog) and dlg.windowTitle() == "UI licence"
    ]
    assert ui_dialogs, "Expected a UI licence dialog to be open"
    ui_dlg = ui_dialogs[-1]

    ui_editor = ui_dlg.findChild(QPlainTextEdit, "LicenceText")
    assert ui_editor is not None
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in ui_editor.toPlainText()

    ui_dlg.close()
    qapp.processEvents()

    btn_backend.click()
    qapp.processEvents()

    backend_dialogs = [
        dlg
        for dlg in QApplication.topLevelWidgets()
        if isinstance(dlg, QDialog) and dlg.windowTitle() == "Backend licence"
    ]
    assert backend_dialogs, "Expected a Backend licence dialog to be open"
    backend_dlg = backend_dialogs[-1]

    # Backend licence dialog should be narrower than the UI LGPL dialog.
    assert backend_dlg.width() <= 520

    backend_editor = backend_dlg.findChild(QPlainTextEdit, "LicenceText")
    assert backend_editor is not None
    assert "GNU GENERAL PUBLIC LICENSE" in backend_editor.toPlainText()

    backend_dlg.close()
    qapp.processEvents()
