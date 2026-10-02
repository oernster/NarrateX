from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from installer.state.model import Operation

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow


def uninstall_confirmation_text(remove_user_data: bool) -> str:
    """What the confirmation says, matching what the uninstall will do."""

    if remove_user_data:
        return (
            "This will uninstall NarrateX for the current user and delete its "
            "user data: your bookmarks, the shelf index, your preferences, the "
            "voices folder, converted books and the cache. This cannot be undone."
        )
    return (
        "This will uninstall NarrateX for the current user. Your user data is "
        "kept: bookmarks, the shelf index, preferences and the rest stay where "
        "they are."
    )


def confirm_and_run_uninstall(window: InstallerMainWindow) -> None:
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("Confirm uninstall")
    box.setText(uninstall_confirmation_text(window._remove_user_data))
    uninstall_btn = box.addButton("Uninstall", QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() == uninstall_btn:
        window._request_operation(Operation.UNINSTALL)
