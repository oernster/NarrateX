"""Main installer window (Stellody-like UI)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from installer.constants import InstallerIdentity
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.install_ops import InstallOptions, install_new, upgrade_or_reinstall
from installer.ops.repair_ops import RepairOptions, repair
from installer.ops.uninstall_ops import UninstallOptions, uninstall_with_feedback
from installer.state.model import InstalledInfo, InstallerState, Operation
from installer.state.registry import read_uninstall_entry
from installer.ui.themes import DARK, LIGHT, Theme
from installer.ui.worker import OperationController, OperationResult
from installer.ui.icons import build_installer_window_icon
from installer.ui.licence_dialog import InstallerLicenceDialog
from voice_reader.shared.resources import find_qt_window_icon_path
from voice_reader.version import APP_NAME, __version__


@dataclass(frozen=True, slots=True)
class UiSelections:
    install_dir: Path
    shortcut_desktop: bool
    shortcut_start_menu: bool


class InstallerMainWindow(QMainWindow):
    operationRequested = Signal(str, object)

    def __init__(self, cli_args) -> None:  # noqa: ANN001 (Qt entrypoint)
        super().__init__()

        if os.name != "nt":
            raise RuntimeError("Installer UI is Windows-only")

        self._cli_args = cli_args
        self._identity = InstallerIdentity()
        self._op_controller = OperationController()

        # Default to dark mode (per UX requirement).
        self._theme: Theme = DARK

        self.setWindowTitle(f"{APP_NAME} Setup")
        # Reduce vertical waste.
        self.setFixedSize(620, 520)

        # Window icon (taskbar/titlebar). This is separate from the exe icon.
        try:
            from PySide6.QtGui import QIcon

            icon = build_installer_window_icon(
                project_root=Path(__file__).resolve().parents[2]
            )
            if not icon.isNull():
                self.setWindowIcon(icon)
            else:
                icon_path = find_qt_window_icon_path(
                    project_root=Path(__file__).resolve().parents[2]
                )
                if icon_path is not None:
                    self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        self._build_ui()
        self._apply_theme()
        self._refresh_state()

        # If invoked as uninstaller from Settings.
        if getattr(cli_args, "uninstall", False):
            self._confirm_and_run_uninstall()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(36, 24, 36, 20)
        outer.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title = QLabel(f"{APP_NAME} Setup")
        title.setObjectName("HeaderTitle")

        version = QLabel(f"v{__version__}")
        version.setObjectName("HeaderVersion")
        version.setAlignment(Qt.AlignVCenter)

        header_left = QHBoxLayout()
        header_left.setSpacing(14)
        header_left.addWidget(title)
        header_left.addWidget(version)
        header_left.addItem(QSpacerItem(10, 10))

        self._licence_btn = QPushButton("Licence")
        self._licence_btn.setObjectName("LicenceButton")
        self._licence_btn.setToolTip("Installer licence")
        self._licence_btn.clicked.connect(self._show_installer_licence)

        self._theme_toggle_btn = QPushButton(self._theme.toggle_label)
        self._theme_toggle_btn.setObjectName("ThemeToggle")
        self._theme_toggle_btn.clicked.connect(self._toggle_theme)

        header_row.addLayout(header_left)
        header_row.addStretch(1)
        header_row.addWidget(self._licence_btn)
        header_row.addWidget(self._theme_toggle_btn)

        outer.addLayout(header_row)

        self._subtitle = QLabel(f"Welcome to the {APP_NAME} Installer")
        self._subtitle.setObjectName("SubTitle")
        self._subtitle.setAlignment(Qt.AlignHCenter)
        outer.addWidget(self._subtitle)

        self._status_line = QLabel("")
        self._status_line.setObjectName("StatusLine")
        self._status_line.setWordWrap(True)
        self._status_line.setAlignment(Qt.AlignHCenter)
        outer.addWidget(self._status_line)

        # Install directory picker row (always present; used for install/upgrade/reinstall)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)

        self._install_dir_edit = QLineEdit()
        self._install_dir_edit.setPlaceholderText("Installation directory")
        self._install_dir_edit.setText(str(self._default_install_dir()))

        browse = QPushButton("Browse")
        browse.setObjectName("BrowseButton")
        browse.clicked.connect(self._browse_install_dir)

        dir_row.addWidget(self._install_dir_edit, 1)
        dir_row.addWidget(browse)
        outer.addLayout(dir_row)

        self._desktop_cb = QCheckBox("Create desktop shortcut")
        self._desktop_cb.setChecked(True)
        self._startmenu_cb = QCheckBox("Create Start menu shortcut")
        self._startmenu_cb.setChecked(True)
        outer.addWidget(self._desktop_cb)
        outer.addWidget(self._startmenu_cb)

        outer.addSpacing(10)

        self._actions_row = QHBoxLayout()
        self._actions_row.setSpacing(18)

        # Center primary actions robustly.
        #
        # We use symmetric stretches on both sides so when only one of the two
        # primary buttons is visible, it stays centered (it should not shift
        # left/right during state changes).
        self._actions_row.addStretch(1)

        self._btn_primary_left = QPushButton("Install")
        self._btn_primary_left.setObjectName("PrimaryAction")
        self._btn_primary_left.clicked.connect(
            lambda: self._request_operation(Operation.INSTALL)
        )

        self._btn_primary_right = QPushButton("Repair")
        self._btn_primary_right.setObjectName("PrimaryAction")
        self._btn_primary_right.clicked.connect(
            lambda: self._request_operation(Operation.REPAIR)
        )

        self._actions_row.addWidget(self._btn_primary_left)
        self._actions_row.addWidget(self._btn_primary_right)
        self._actions_row.addStretch(1)
        outer.addLayout(self._actions_row)

        self._btn_uninstall = QPushButton("Uninstall")
        self._btn_uninstall.setObjectName("DangerAction")
        self._btn_uninstall.clicked.connect(
            lambda: self._request_operation(Operation.UNINSTALL)
        )
        outer.addWidget(self._btn_uninstall, alignment=Qt.AlignHCenter)

        # Keep the bottom area visually balanced (avoid a huge empty gap).
        outer.addStretch(0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("ProgressBar")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        self._progress = QLabel("")
        self._progress.setObjectName("StatusLine")
        self._progress.setAlignment(Qt.AlignHCenter)
        outer.addWidget(self._progress)

    def _apply_theme(self) -> None:
        self.setStyleSheet(self._theme.qss)
        self._theme_toggle_btn.setText(self._theme.toggle_label)

    def _toggle_theme(self) -> None:
        self._theme = DARK if self._theme is LIGHT else LIGHT
        self._apply_theme()

    def _show_installer_licence(self) -> None:
        # Keep a reference so the dialog is not garbage-collected immediately.
        existing = getattr(self, "_installer_licence_dialog", None)
        if isinstance(existing, QDialog):
            try:
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                pass

        dlg = InstallerLicenceDialog(parent=self)
        self._installer_licence_dialog = dlg

        def _clear_ref() -> None:
            try:
                if getattr(self, "_installer_licence_dialog", None) is dlg:
                    self._installer_licence_dialog = None
            except Exception:
                pass

        try:
            dlg.finished.connect(_clear_ref)
        except Exception:
            pass

        # Non-blocking but modal.
        dlg.open()

    def _default_install_dir(self) -> Path:
        local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / APP_NAME

    def _browse_install_dir(self) -> None:
        current = Path(
            self._install_dir_edit.text().strip() or str(self._default_install_dir())
        )
        chosen = QFileDialog.getExistingDirectory(
            self, "Select installation directory", str(current)
        )
        if chosen:
            self._install_dir_edit.setText(chosen)

    def _refresh_state(self) -> None:
        entry = read_uninstall_entry(self._identity.uninstall_key)
        installed = None
        if entry and entry.install_location.exists():
            exe = entry.install_location / "NarrateX.exe"
            if exe.exists():
                installed = InstalledInfo(
                    version=entry.display_version, location=entry.install_location
                )

        state = InstallerState(installer_version=__version__, installed=installed)
        self._state = state

        self._status_line.setText(state.status_line(APP_NAME))

        allowed = state.allowed_operations()
        self._set_buttons_for_allowed_ops(allowed)

        # Set checkboxes to persisted values if available.
        if entry is not None:
            if entry.shortcut_desktop is not None:
                self._desktop_cb.setChecked(entry.shortcut_desktop)
            if entry.shortcut_start_menu is not None:
                self._startmenu_cb.setChecked(entry.shortcut_start_menu)

            # On upgrade/reinstall, default directory to current install dir.
            self._install_dir_edit.setText(str(entry.install_location))

    def _set_buttons_for_allowed_ops(
        self, allowed: set[Operation] | frozenset[Operation]
    ) -> None:
        # Primary buttons are shown in the center row. We use up to two.
        # Uninstall is shown separately in red.
        self._btn_uninstall.setVisible(Operation.UNINSTALL in allowed)

        primary_ops: list[Operation] = [
            op
            for op in [
                Operation.INSTALL,
                Operation.UPGRADE,
                Operation.REINSTALL,
                Operation.REPAIR,
            ]
            if op in allowed
        ]
        left = primary_ops[0] if primary_ops else None
        right = primary_ops[1] if len(primary_ops) > 1 else None

        def _label(op: Operation) -> str:
            return {
                Operation.INSTALL: "Install",
                Operation.UPGRADE: "Upgrade",
                Operation.REINSTALL: "Reinstall",
                Operation.REPAIR: "Repair",
            }[op]

        if left is None:
            self._btn_primary_left.setVisible(False)
        else:
            self._btn_primary_left.setVisible(True)
            self._btn_primary_left.setText(_label(left))
            try:
                self._btn_primary_left.clicked.disconnect()
            except Exception:
                pass
            self._btn_primary_left.clicked.connect(
                lambda: self._request_operation(left)
            )

        if right is None:
            self._btn_primary_right.setVisible(False)
        else:
            self._btn_primary_right.setVisible(True)
            self._btn_primary_right.setText(_label(right))
            try:
                self._btn_primary_right.clicked.disconnect()
            except Exception:
                pass
            self._btn_primary_right.clicked.connect(
                lambda: self._request_operation(right)
            )

    def _validate_install_dir(self, path: Path) -> bool:
        # Best-effort check that the directory is user-writeable.
        try:
            path.mkdir(parents=True, exist_ok=True)
            test = path / ".narratex_installer_write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def _current_selections(self) -> UiSelections:
        p = Path(
            self._install_dir_edit.text().strip() or str(self._default_install_dir())
        )
        return UiSelections(
            install_dir=p,
            shortcut_desktop=bool(self._desktop_cb.isChecked()),
            shortcut_start_menu=bool(self._startmenu_cb.isChecked()),
        )

    def _request_operation(self, op: Operation) -> None:
        selections = self._current_selections()
        if op in {Operation.INSTALL, Operation.UPGRADE, Operation.REINSTALL}:
            if not self._validate_install_dir(selections.install_dir):
                QMessageBox.critical(
                    self,
                    "Invalid installation directory",
                    "The selected installation directory is not writable without administrator privileges.",
                )
                return

        if self._op_controller.is_running:
            return

        # Immediately reflect that the operation has begun.
        # This also forces a re-read of the registry after install/uninstall so
        # button states update without requiring a relaunch.
        self._refresh_state()

        self._set_ui_busy(True)
        self._progress.setText("Working...")
        self._progress_bar.setValue(0)

        fn, kwargs = self._operation_callable(op, selections)
        self._debug_last_op = op
        self._debug_last_kwargs = kwargs
        self._op_controller.start(
            fn,
            kwargs=kwargs,
            on_progress=self._on_progress,
            on_finished=lambda r: self._on_operation_finished(op, r),
            on_app_running=lambda msg: self._on_app_running(op, msg),
        )

    def _on_progress(self, payload) -> None:  # noqa: ANN001
        # payload can be:
        # - str message
        # - {"pct": int, "message": str}
        if isinstance(payload, dict):
            pct = payload.get("pct")
            msg = payload.get("message", "")
            if isinstance(pct, int):
                self._progress_bar.setValue(max(0, min(100, pct)))
            if msg:
                self._progress.setText(str(msg))
            return

        if isinstance(payload, str) and payload:
            self._progress.setText(payload)

    def closeEvent(self, event) -> None:  # noqa: ANN001 (Qt override)
        if self._op_controller.is_running:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Operation in progress")
            box.setText("An operation is running. Do you want to cancel and exit?")
            cancel_exit = box.addButton("Cancel && Exit", QMessageBox.AcceptRole)
            box.addButton("Keep running", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == cancel_exit:
                self._progress.setText("Cancelling...")
                self._op_controller.force_stop(timeout_ms=1500)
                event.accept()
                return
            event.ignore()
            return
        event.accept()

    def _set_ui_busy(self, busy: bool) -> None:
        self._progress_bar.setVisible(busy)
        for w in [
            self._btn_primary_left,
            self._btn_primary_right,
            self._btn_uninstall,
            self._licence_btn,
            self._theme_toggle_btn,
            self._install_dir_edit,
            self._desktop_cb,
            self._startmenu_cb,
        ]:
            w.setEnabled(not busy)

    def _on_app_running(self, op: Operation, msg: str) -> None:
        self._set_ui_busy(False)
        self._progress.setText("")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(f"{APP_NAME} is running")
        box.setText(f"Please close {APP_NAME} and click Retry.")
        retry = box.addButton("Retry", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == retry:
            self._request_operation(op)

    def _on_operation_finished(self, op: Operation, result: OperationResult) -> None:
        self._set_ui_busy(False)
        if result.ok:
            self._progress_bar.setValue(100)
            if op == Operation.UNINSTALL:
                self._progress.setText("Uninstalled")
            else:
                self._progress.setText("Done")
        else:
            if result.message and result.message != "app_running":
                QMessageBox.critical(self, "Operation failed", result.message)
            self._progress.setText("")
            self._progress_bar.setValue(0)

        self._refresh_state()

        # Keep completion visible briefly so users can tell something happened
        # (especially for fast operations like uninstall scheduling).
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(1200, lambda: self._progress.setText(""))
        except Exception:
            pass

        if op == Operation.UNINSTALL and result.ok:
            # Only auto-close when we were explicitly launched as an uninstaller
            # (e.g. from Windows Settings via UninstallString).
            if getattr(self._cli_args, "uninstall", False):
                try:
                    from PySide6.QtCore import QTimer

                    QTimer.singleShot(600, self.close)
                except Exception:
                    self.close()
            return

        return

    def _operation_callable(self, op: Operation, selections: UiSelections):
        entry = read_uninstall_entry(self._identity.uninstall_key)
        current_install_dir = entry.install_location if entry else None

        if op == Operation.INSTALL:
            return (
                install_new,
                {
                    "identity": self._identity,
                    "opts": InstallOptions(
                        target_dir=selections.install_dir,
                        create_desktop_shortcut=selections.shortcut_desktop,
                        create_start_menu_shortcut=selections.shortcut_start_menu,
                    ),
                },
            )

        if op in {Operation.UPGRADE, Operation.REINSTALL}:
            if current_install_dir is None:
                raise InstallerOperationError("No existing installation detected")
            return (
                upgrade_or_reinstall,
                {
                    "identity": self._identity,
                    "current_install_dir": current_install_dir,
                    "opts": InstallOptions(
                        target_dir=selections.install_dir,
                        create_desktop_shortcut=selections.shortcut_desktop,
                        create_start_menu_shortcut=selections.shortcut_start_menu,
                    ),
                },
            )

        if op == Operation.REPAIR:
            return (
                repair,
                {
                    "identity": self._identity,
                    "opts": RepairOptions(
                        restore_desktop_shortcut=selections.shortcut_desktop,
                        restore_start_menu_shortcut=selections.shortcut_start_menu,
                    ),
                },
            )

        if op == Operation.UNINSTALL:
            return (
                uninstall_with_feedback,
                {
                    "identity": self._identity,
                    "opts": UninstallOptions(remove_user_data=True),
                },
            )

        raise InstallerOperationError(f"Unsupported operation: {op}")

    # Synchronous runner removed: operations run in background via OperationController.

    def _confirm_and_run_uninstall(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Confirm uninstall")
        box.setText(
            "This will uninstall NarrateX for the current user and remove user data (voices/cache/temp_books)."
        )
        uninstall_btn = box.addButton("Uninstall", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == uninstall_btn:
            self._request_operation(Operation.UNINSTALL)
