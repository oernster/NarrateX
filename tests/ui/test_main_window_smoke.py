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


def test_main_window_play_pause_button_exists(qapp) -> None:
    del qapp
    w = MainWindow()
    assert hasattr(w, "btn_play_pause")
    assert w.btn_play_pause.objectName() == "playPauseButton"
    assert w.btn_play_pause.toolTip() in {"Play", "Pause"}


def test_main_window_remove_book_button_exists_and_starts_locked(qapp) -> None:
    del qapp
    w = MainWindow()
    assert hasattr(w, "btn_remove_book")
    assert not w.btn_remove_book.icon().isNull()
    assert w.btn_remove_book.isEnabled() is False
    assert "file is kept" in w.btn_remove_book.toolTip()


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
    # UX default is 25% until user preferences are applied by the controller.
    assert w.volume_slider.value() == 25

    assert hasattr(w, "lbl_volume_icon")
    assert not w.lbl_volume_icon.icon().isNull()

    # The keyboard stop for volume is the speaker button, never the slider.
    from PySide6.QtCore import Qt

    assert w.volume_slider.focusPolicy() == Qt.NoFocus
    assert w.lbl_volume_icon.keeb_volume_slider is w.volume_slider


def test_tab_ring_follows_visual_order_and_wraps(qapp) -> None:
    """The transport row runs left to right; the foot strip closes the ring."""

    from PySide6.QtCore import Qt

    from voice_reader.ui.main_window import _NeutralStart

    w = MainWindow()
    w.show()
    qapp.processEvents()
    w.set_chapter_controls_enabled(previous=True, next_=True)
    # The reader is a stop only while its text overflows it.
    w.set_reader_text(" ".join(["words"] * 20000))
    qapp.processEvents()

    def next_stop(widget):
        # `nextInFocusChain` is the raw chain, which holds widgets Tab would
        # never reach. Qt skips a disabled or hidden stop, so the walk skips
        # them too; otherwise the shelf's controls, sitting on the page that is
        # not showing, would read as stops the reader can never tab to.
        nxt = widget.nextInFocusChain()
        while (
            not (nxt.focusPolicy() & Qt.TabFocus)
            or isinstance(nxt, _NeutralStart)
            or not nxt.isEnabled()
            or not nxt.isVisible()
        ):
            nxt = nxt.nextInFocusChain()
        return nxt

    assert next_stop(w.speed_combo) is w.lbl_volume_icon
    assert next_stop(w.lbl_volume_icon) is w.btn_bookmarks
    assert next_stop(w.btn_help) is w.btn_prev_chapter
    assert next_stop(w.btn_prev_chapter) is w.btn_play_pause
    assert next_stop(w.btn_play_pause) is w.btn_stop
    assert next_stop(w.btn_stop) is w.btn_next_chapter
    assert next_stop(w.btn_next_chapter) is w.reader
    assert next_stop(w.reader) is w.bottom_tray.donate_button
    assert next_stop(w.bottom_tray.donate_button) is w.btn_ui_licence
    assert next_stop(w.btn_ui_licence) is w.btn_backend_licence
    assert next_stop(w.btn_backend_licence) is w.btn_select_book
    w.close()


def test_main_window_licence_buttons_open_dialogs(qapp) -> None:
    """Smoke test for the two licence buttons in the foot strip."""

    from PySide6.QtWidgets import QApplication, QDialog, QTextBrowser, QToolButton

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

    ui_editor = ui_dlg.findChild(QTextBrowser, "LicenceText")
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

    backend_editor = backend_dlg.findChild(QTextBrowser, "LicenceText")
    assert backend_editor is not None
    assert "GNU GENERAL PUBLIC LICENSE" in backend_editor.toPlainText()

    backend_dlg.close()
    qapp.processEvents()


def test_a_long_status_message_is_never_cut_off(qapp) -> None:
    """The no-text failure names the book, then the reason, at any width.

    Seen cut off mid-word in the installed build: a single-line label beside a
    stretch ran out of room at the window's narrowest. It wraps instead.
    """

    from PySide6.QtCore import QRect, Qt

    from voice_reader.shared.errors import BookHasNoTextError

    w = MainWindow()
    w.resize(w.minimumSizeHint().width(), w.height())
    w.show()
    text = f"Failed loading New Scientist - 19 April 2014.pdf: {BookHasNoTextError()}"
    w.lbl_status.setText(text)
    w.lbl_status.setMaximumWidth(
        w.lbl_status.fontMetrics().horizontalAdvance(text) // 2
    )
    qapp.processEvents()
    label = w.lbl_status
    room = label.contentsRect()
    needed = label.fontMetrics().boundingRect(
        QRect(0, 0, room.width(), room.height() * 100), Qt.TextWordWrap, label.text()
    )
    assert needed.width() <= room.width()
    assert needed.height() <= room.height()
    w.close()
