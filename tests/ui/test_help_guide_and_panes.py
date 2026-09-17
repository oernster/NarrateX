"""Help | Guide, auto-scroll on read-through surfaces and panes that are not stops."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QDialog,
    QPlainTextEdit,
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

_LONG_TEXT = "\n".join(f"line {n}" for n in range(400))
_TICKS_PER_SECOND = 1000 // AutoScroller.TICK_MS


def _dispose(*widgets) -> None:
    """Close and delete what a test built, before the shared window cleanup."""

    from PySide6.QtCore import QCoreApplication, QEvent as _Event

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, _Event.Type.DeferredDelete)


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
    _dispose(w._help_menu, menu, w._guide_dialog, w)  # noqa: SLF001


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
    editor = QPlainTextEdit(dialog)
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
    assert editor.focusPolicy() == Qt.FocusPolicy.StrongFocus
    _dispose(dialog)


def _stops(window) -> list:
    window.show()
    QApplication.processEvents()
    start = window.focusWidget() or window
    start.setFocus()
    seen, widget = [], start
    for _ in range(200):
        widget = widget.nextInFocusChain()
        if widget is start:
            break
        policy = widget.focusPolicy()
        if (
            policy & Qt.FocusPolicy.TabFocus
            and widget.isVisible()
            and widget.isEnabled()
        ):
            seen.append(widget)
    return seen


def test_no_surface_offers_a_region_that_scrolls_nowhere(qapp) -> None:
    del qapp
    main = MainWindow()
    main.resize(1200, 700)
    surfaces = [
        main,
        GuideDialog(),
        PlainTextLicenceDialog(title="UI licence", text="short"),
        PlainTextLicenceDialog(title="UI licence", text=_LONG_TEXT),
    ]
    from installer.ui.licence_dialog import InstallerLicenceDialog

    surfaces.append(InstallerLicenceDialog())
    for surface in surfaces:
        for stop in _stops(surface):
            if isinstance(stop, QAbstractScrollArea) and not stop.inherits(
                "QAbstractItemView"
            ):
                assert (
                    stop.verticalScrollBar().maximum() > 0
                    or stop.horizontalScrollBar().maximum() > 0
                ), f"{type(stop).__name__} in {surface.windowTitle()} fits yet is a stop"
    _dispose(*surfaces)


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
    _dispose(*dialogs, main)


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
    _dispose(dialog)


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
    _dispose(modal)

    # Content that fits never moves.
    short, short_editor = _text_dialog("short")
    short.show()
    qapp.processEvents()
    idle = AutoScroller(short_editor)
    idle.timer.stop()
    for _ in range(_TICKS_PER_SECOND):
        idle.tick()
    assert short_editor.verticalScrollBar().value() == 0
    _dispose(short, dialog)
