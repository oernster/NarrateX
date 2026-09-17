"""No pane is a keyboard stop, on any window or dialog in the app or installer.

Focus belongs to controls. A pane (a panel widget, a frame, a label, a scroll
area) holds them; a ring on it tells the reader nothing and costs a key press
to step past. The one region allowed is read-only text while it overflows,
since otherwise the keyboard could not scroll it.

The walk follows Qt's own focus chain rather than the child list, so what it
reaches is what a real Tab press reaches.
"""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTabBar,
    QTextEdit,
)

from tests.ui._dispose_testkit import dispose

_LONG_TEXT = "\n".join(f"line {n}" for n in range(400))
_CHAIN_LIMIT = 200
_CONTROLS = (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QTabBar,
)


def _stops(window) -> list:
    """Every stop in the window's chain, walked from the window itself.

    Starting at the window rather than at the focused widget matters: the
    widget holding focus on open is exactly the one a walk from it skips.
    """

    window.show()
    QApplication.processEvents()
    seen, widget = [], window
    for _ in range(_CHAIN_LIMIT):
        widget = widget.nextInFocusChain()
        if widget is window:
            break
        policy = widget.focusPolicy()
        if (
            policy & Qt.FocusPolicy.TabFocus
            and widget.isVisible()
            and widget.isEnabled()
        ):
            seen.append(widget)
    return seen


def _overflows(area) -> bool:
    return (
        area.verticalScrollBar().maximum() > 0
        or area.horizontalScrollBar().maximum() > 0
    )


def _is_reading_text(widget) -> bool:
    return isinstance(widget, (QTextEdit, QPlainTextEdit)) and widget.isReadOnly()


def pane_offence(stop) -> str | None:
    """Why `stop` should not be a stop; None when it is a legitimate one."""

    from voice_reader.ui.main_window import _NeutralStart

    name = type(stop).__name__
    # The launch focus sink: 0x0, never painted, gone from the ring once left.
    if isinstance(stop, (_CONTROLS, _NeutralStart)):
        return None
    if isinstance(stop, (QTextEdit, QPlainTextEdit)) and not stop.isReadOnly():
        return None
    if _is_reading_text(stop):
        if stop.focusPolicy() & Qt.FocusPolicy.ClickFocus:
            return f"{name} is a reading pane a click would ring"
        if _overflows(stop):
            return None
        return f"{name} is read-only text that scrolls nowhere"
    return f"{name} holds controls rather than being one"


def _surfaces(monkeypatch, tmp_path) -> list:
    from installer.ui import main_window as installer_window
    from installer.ui.licence_dialog import InstallerLicenceDialog
    from voice_reader.ui._help_dialogs import build_about_dialog
    from voice_reader.ui.bookmarks_dialog import (
        BookmarksDialog,
        BookmarksDialogActions,
    )
    from voice_reader.ui.guide_dialog import GuideDialog
    from voice_reader.ui.ideas_dialog import IdeasDialog, IdeasDialogActions
    from voice_reader.ui.licence_dialog import PlainTextLicenceDialog
    from voice_reader.ui.main_window import MainWindow
    from voice_reader.ui.structural_bookmarks_dialog import (
        StructuralBookmarksDialog,
        StructuralBookmarksDialogActions,
    )
    from voice_reader.version import __version__

    empty = MainWindow()
    reading = MainWindow()
    reading.reader.setPlainText(_LONG_TEXT)
    surfaces = [
        empty,
        reading,
        GuideDialog(),
        PlainTextLicenceDialog(title="UI licence", text="short"),
        PlainTextLicenceDialog(title="UI licence", text=_LONG_TEXT),
        build_about_dialog(parent=empty, on_check_updates=lambda: None),
        BookmarksDialog(
            parent=None,
            actions=BookmarksDialogActions(
                list_bookmarks=lambda: [],
                add_bookmark=lambda: None,
                go_to_bookmark=lambda _b: None,
                delete_bookmark=lambda _b: None,
            ),
        ),
        IdeasDialog(
            parent=None,
            actions=IdeasDialogActions(list_items=lambda: [], go_to=lambda _i: None),
            book_title="Book",
        ),
        StructuralBookmarksDialog(
            parent=None,
            actions=StructuralBookmarksDialogActions(
                list_items=lambda: [], go_to=lambda _i: None
            ),
            book_title="Book",
        ),
        InstallerLicenceDialog(),
    ]
    monkeypatch.setattr(installer_window, "read_uninstall_entry", lambda _key: None)
    surfaces.append(
        installer_window.InstallerMainWindow(SimpleNamespace(uninstall=False))
    )
    (tmp_path / "NarrateX.exe").write_bytes(b"stub")
    installed = SimpleNamespace(
        display_version=__version__,
        install_location=tmp_path,
        shortcut_desktop=True,
        shortcut_start_menu=True,
    )
    monkeypatch.setattr(
        installer_window, "read_uninstall_entry", lambda _key: installed
    )
    surfaces.append(
        installer_window.InstallerMainWindow(SimpleNamespace(uninstall=False))
    )
    return surfaces


# Each walk happens inside a helper that answers strings; the test body then
# holds no widget once the helper has disposed of them.


def _every_surface_offence(monkeypatch, tmp_path) -> list[str]:
    surfaces = _surfaces(monkeypatch, tmp_path)
    found = []
    for surface in surfaces:
        for stop in _stops(surface):
            offence = pane_offence(stop)
            if offence is not None:
                found.append(f"{type(surface).__name__}: {offence}")
        opened_on = surface.focusWidget()
        if _is_reading_text(opened_on):
            found.append(f"{type(surface).__name__}: opens on its reading pane")
    dispose(*surfaces)
    return found


def test_no_surface_offers_a_pane_as_a_stop(qapp, monkeypatch, tmp_path) -> None:
    del qapp
    assert _every_surface_offence(monkeypatch, tmp_path) == []


def _planted_offences() -> list:
    from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout

    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    layout.addWidget(QScrollArea(dialog))
    layout.addWidget(QPushButton("Close", dialog))
    QTextEdit(dialog).setReadOnly(True)
    QTextEdit(dialog)
    clickable = QTextEdit(dialog)
    clickable.setReadOnly(True)
    clickable.setPlainText(_LONG_TEXT)
    offences = [pane_offence(stop) for stop in _stops(dialog)]
    dispose(dialog)
    return offences


def test_the_walk_catches_a_pane_that_takes_focus(qapp) -> None:
    """The guard bites: a scroll area left at Qt's default is reported."""

    del qapp
    assert _planted_offences() == [
        "QScrollArea holds controls rather than being one",
        None,
        "QTextEdit is a reading pane a click would ring",
        None,
        "QTextEdit is a reading pane a click would ring",
    ]


def _opening_focus(dialog_class) -> tuple[str, str]:
    from PySide6.QtWidgets import QPushButton, QVBoxLayout

    dialog = dialog_class()
    layout = QVBoxLayout(dialog)
    text = QTextEdit(dialog)
    text.setReadOnly(True)
    layout.addWidget(text)
    layout.addWidget(QPushButton("Close", dialog))
    dialog.show()
    QApplication.processEvents()
    answer = type(dialog.focusWidget()).__name__
    only_pane = dialog_class()
    QVBoxLayout(only_pane).addWidget(QTextEdit(only_pane))
    only_pane.show()
    only_pane.hide()
    # Opened again: the first stop is chosen on the first opening only.
    only_pane.show()
    QApplication.processEvents()
    stop = str(only_pane.first_stop()) if hasattr(only_pane, "first_stop") else ""
    dispose(dialog, only_pane)
    return answer, stop


def test_a_dialog_opens_on_its_control_never_on_its_pane(qapp) -> None:
    """Plain QDialog opens on the pane (the defect); FirstStopDialog does not."""

    from PySide6.QtWidgets import QDialog

    from voice_reader.ui.first_stop_dialog import FirstStopDialog

    del qapp
    assert _opening_focus(QDialog)[0] == "QTextEdit"
    assert _opening_focus(FirstStopDialog) == ("QPushButton", "None")
