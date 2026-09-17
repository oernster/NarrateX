"""Help | Guide, auto-scroll on read-through surfaces and panes that are not stops."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QTextBrowser,
    QPushButton,
    QVBoxLayout,
)

from voice_reader.ui import main_window as main_window_module
from voice_reader.ui.artwork import Artwork, artwork_path
from voice_reader.ui.auto_scroller import AutoScroller
from voice_reader.ui.guide_dialog import NOT_LISTED, GuideDialog, guide_html
from voice_reader.ui.licence_dialog import PlainTextLicenceDialog
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.pane_focus import follow_overflow
from tests.ui._dispose_testkit import dispose

_LONG_TEXT = "\n".join(f"line {n}" for n in range(400))
_TICKS_PER_SECOND = 1000 // AutoScroller.TICK_MS


def _ticks(ms: int) -> int:
    return -(-ms // AutoScroller.TICK_MS)


def test_help_menu_offers_the_guide_first_then_about(qapp, monkeypatch) -> None:
    del qapp
    w = MainWindow()
    menu = w.build_help_menu()
    assert [a.text() for a in menu.actions()] == ["Guide", "About NarrateX"]
    assert w.btn_help.toolTip() == "Help"

    opened: list[str] = []
    monkeypatch.setattr(w, "show_about_dialog", lambda: opened.append("about"))
    w.show_help_menu()
    assert w._help_menu.actions()[0].text() == "Guide"  # noqa: SLF001
    menu.actions()[0].trigger()
    assert isinstance(w._guide_dialog, GuideDialog)  # noqa: SLF001
    dispose(w._help_menu, menu, w._guide_dialog, w)  # noqa: SLF001


def test_the_guide_shows_every_control_picture(qapp) -> None:
    del qapp
    html = guide_html()
    for name in Artwork:
        url = f"file:///{artwork_path(name).as_posix()}"
        assert (url in html) is (name not in NOT_LISTED), name


def test_a_missing_picture_is_left_out_rather_than_broken(qapp, monkeypatch) -> None:
    del qapp
    from voice_reader.ui import guide_dialog

    monkeypatch.setattr(
        guide_dialog, "artwork_path", lambda name: artwork_path(name).with_name("x")
    )
    assert "<img" not in guide_dialog.guide_html()


def _text_dialog(text: str):
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    editor = QTextBrowser(dialog)
    editor.setPlainText(text)
    layout.addWidget(editor)
    layout.addWidget(QPushButton("Close", dialog))
    dialog.resize(300, 200)
    return dialog, editor


def test_a_region_is_a_stop_only_while_it_overflows(qapp) -> None:
    dialog, editor = _text_dialog("short")
    focus = follow_overflow(editor)
    dialog.show()
    qapp.processEvents()
    assert not focus.overflows()
    assert editor.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert editor.viewport().focusPolicy() == Qt.FocusPolicy.NoFocus

    editor.setPlainText(_LONG_TEXT)
    qapp.processEvents()
    assert focus.overflows()
    # Tab reaches it; a click never does, so a click never rings it.
    assert editor.focusPolicy() == Qt.FocusPolicy.TabFocus
    dispose(dialog)


def test_read_through_surfaces_wear_the_scroller(qapp) -> None:
    del qapp
    from installer.ui.licence_dialog import InstallerLicenceDialog

    dialogs = (
        GuideDialog(),
        PlainTextLicenceDialog(title="t", text="x"),
        InstallerLicenceDialog(),
    )
    for dialog in dialogs:
        assert isinstance(dialog.scroller, AutoScroller)
    main = main_window_module.MainWindow()
    assert not hasattr(main, "reader_scroller")
    dispose(*dialogs, main)


def test_the_scroller_runs_the_whole_cycle(qapp) -> None:
    dialog, editor = _text_dialog(_LONG_TEXT)
    dialog.show()
    qapp.processEvents()
    scroller = AutoScroller(editor)
    assert scroller.timer.isActive()
    scroller.timer.stop()
    bar = editor.verticalScrollBar()
    maximum = bar.maximum()
    assert maximum > 0

    # Opening focus is not a reader: the start hold survives it.
    editor.setFocus()
    qapp.processEvents()
    for _ in range(_ticks(AutoScroller.START_PAUSE_MS) - 1):
        scroller.tick()
    assert bar.value() == 0 and scroller.phase == AutoScroller.PAUSE_TOP
    scroller.tick()
    assert scroller.phase == AutoScroller.DOWN

    for _ in range(AutoScroller.DOWN_TICKS_PER_STEP):
        scroller.tick()
    assert bar.value() == AutoScroller.DOWN_STEP_PX

    bar.setValue(maximum - AutoScroller.DOWN_STEP_PX)
    for _ in range(AutoScroller.DOWN_TICKS_PER_STEP):
        scroller.tick()
    assert scroller.phase == AutoScroller.PAUSE_BOTTOM
    for _ in range(_ticks(AutoScroller.BOTTOM_PAUSE_MS)):
        scroller.tick()
    assert scroller.phase == AutoScroller.UP
    scroller.tick()
    assert bar.value() == maximum - AutoScroller.UP_STEP_PX

    bar.setValue(AutoScroller.UP_STEP_PX)
    scroller.tick()
    assert bar.value() == 0 and scroller.phase == AutoScroller.PAUSE_TOP

    # A wheel is a reader: suspended, then onward from where they stopped.
    wheel = QWheelEvent(
        editor.rect().center(),
        editor.mapToGlobal(editor.rect().center()),
        editor.rect().center() - editor.rect().center(),
        editor.rect().center() - editor.rect().center(),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    assert wheel.type() == QEvent.Type.Wheel
    scroller.eventFilter(editor.viewport(), wheel)
    assert scroller.phase == AutoScroller.MANUAL
    for _ in range(_ticks(AutoScroller.RESUME_AFTER_MS)):
        scroller.tick()
    assert scroller.phase == AutoScroller.DOWN

    # Focus moving in after the hold is a reader too; at the end it rewinds.
    other = QPushButton(dialog)
    other.show()
    other.setFocus()
    qapp.processEvents()
    editor.setFocus()
    qapp.processEvents()
    assert scroller.phase == AutoScroller.MANUAL
    bar.setValue(maximum)
    for _ in range(_ticks(AutoScroller.RESUME_AFTER_MS)):
        scroller.tick()
    assert scroller.phase == AutoScroller.UP
    dispose(dialog)


def test_a_modal_above_freezes_the_surface_and_its_input(qapp) -> None:
    dialog, editor = _text_dialog(_LONG_TEXT)
    dialog.show()
    qapp.processEvents()
    scroller = AutoScroller(editor)
    scroller.timer.stop()
    modal = QDialog()
    modal.setModal(True)
    modal.show()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is modal
    before = scroller.phase
    for _ in range(_ticks(AutoScroller.START_PAUSE_MS) * 2):
        scroller.tick()
    scroller.suspend()
    assert scroller.phase == before
    dispose(modal)

    # Content that fits never moves.
    short, short_editor = _text_dialog("short")
    short.show()
    qapp.processEvents()
    idle = AutoScroller(short_editor)
    idle.timer.stop()
    for _ in range(_TICKS_PER_SECOND):
        idle.tick()
    assert short_editor.verticalScrollBar().value() == 0
    dispose(short, dialog)


def test_licence_text_reads_at_pixel_pace_not_line_pace(qapp) -> None:
    """The licences scrolled a line per step; a step must be one pixel."""

    import pytest
    from PySide6.QtWidgets import QPlainTextEdit

    from installer.ui.licence_dialog import InstallerLicenceDialog
    from voice_reader.ui.licence_dialog import read_licence_text

    for dialog in (
        PlainTextLicenceDialog(title="t", text=read_licence_text("LGPL3-LICENSE")),
        InstallerLicenceDialog(),
    ):
        dialog.show()
        qapp.processEvents()
        bar = dialog.editor.verticalScrollBar()
        # Pixel units: the range far exceeds the text's line count.
        assert bar.maximum() > dialog.editor.toPlainText().count("\n")
        dispose(dialog)
    with pytest.raises(TypeError):
        AutoScroller(QPlainTextEdit())
