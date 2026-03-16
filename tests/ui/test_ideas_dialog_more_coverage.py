from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QMessageBox

from voice_reader.ui import ideas_dialog
from voice_reader.ui.ideas_dialog import IdeaListItem, IdeasDialog, IdeasDialogActions


def test_ideas_dialog_selected_none_branch_smoke(qapp) -> None:
    del qapp

    dlg = IdeasDialog(
        parent=None,
        actions=IdeasDialogActions(list_items=lambda: [], go_to=lambda it: None),
    )
    # No selection => should no-op and set row 0 safely.
    dlg._on_goto()  # noqa: SLF001


def test_ideas_dialog_in_tests_env_helper(qapp, monkeypatch) -> None:
    del qapp
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    assert ideas_dialog._in_tests() is True


def test_ideas_dialog_set_window_flag_exception_is_tolerated(qapp, monkeypatch) -> None:
    del qapp

    # Force setWindowFlag to raise to hit the try/except in IdeasDialog.__init__.
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(IdeasDialog, "setWindowFlag", _boom)

    dlg = IdeasDialog(
        parent=None,
        actions=IdeasDialogActions(list_items=lambda: [], go_to=lambda it: None),
    )
    assert dlg.windowTitle() == "Ideas"


def test_ideas_dialog_error_path_shows_message_box(qapp, monkeypatch) -> None:
    """Exercise the QMessageBox path by forcing _in_tests() False."""

    del qapp
    monkeypatch.setattr(
        __import__("voice_reader.ui.ideas_dialog", fromlist=["_in_tests"]),
        "_in_tests",
        lambda: False,
    )

    def _boom(it: IdeaListItem) -> None:
        raise RuntimeError("boom")

    items = [IdeaListItem(node_id="n1", label="L")]
    dlg = IdeasDialog(
        parent=None,
        actions=IdeasDialogActions(list_items=lambda: items, go_to=_boom),
        book_title="T",
    )
    dlg.show()
    QApplication.processEvents()

    # Ensure selection is present.
    dlg.list.setCurrentRow(0)
    dlg.btn_goto.click()
    QApplication.processEvents()

    boxes = [
        w
        for w in QApplication.topLevelWidgets()
        if isinstance(w, QMessageBox) and w.windowTitle() == "Ideas"
    ]
    assert boxes
    boxes[-1].close()
    dlg.close()

