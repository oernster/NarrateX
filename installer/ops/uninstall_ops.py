"""Uninstall operation."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.progress import (
    COMPLETE_PCT,
    UNINSTALL_READ_PCT,
    UNINSTALL_REGISTRY_PCT,
    UNINSTALL_SCHEDULE_PCT,
    UNINSTALL_SHORTCUTS_PCT,
    UNINSTALL_USER_DATA_PCT,
    report,
)
from installer.ops.running_app import is_app_running
from installer.ops.shortcuts import get_shortcut_paths, remove_shortcut
from installer.state.registry import (
    delete_uninstall_entry,
    read_uninstall_entry,
    try_read_install_location,
)
from voice_reader.version import APP_AUTHOR, APP_NAME


@dataclass(frozen=True, slots=True)
class UninstallOptions:
    remove_user_data: bool = True


def uninstall(
    identity, opts: UninstallOptions, *, progress=None  # noqa: ANN001 (identity)
) -> None:
    if os.name != "nt":
        raise InstallerOperationError("Uninstall is Windows-only")

    entry = read_uninstall_entry(identity.uninstall_key)
    install_dir = None
    if entry is not None:
        install_dir = entry.install_location
    else:
        install_dir = try_read_install_location(identity.uninstall_key)

    if install_dir is None:
        raise InstallerOperationError(
            "NarrateX is not detected as installed for this user"
        )

    install_dir = install_dir.resolve()
    exe = install_dir / "NarrateX.exe"
    if exe.exists() and is_app_running(exe):
        raise AppRunningError("NarrateX is currently running")

    # Remove shortcuts.
    report(progress, pct=UNINSTALL_SHORTCUTS_PCT, message="Removing shortcuts...")
    sp = get_shortcut_paths(identity)
    # If we can't read persisted flags, remove both best-effort.
    if entry is None or entry.shortcut_desktop is not False:
        remove_shortcut(sp.desktop_lnk)
    if entry is None or entry.shortcut_start_menu is not False:
        remove_shortcut(sp.start_menu_lnk)

    report(progress, pct=UNINSTALL_REGISTRY_PCT, message="Removing registry entry...")
    try:
        delete_uninstall_entry(identity.uninstall_key)
    except Exception:  # noqa: BLE001
        # Degrades to a stale Apps and Features entry pointing at files that
        # are about to go. Stopping the uninstall here would leave the user
        # with both the entry and the files, which is strictly worse.
        pass

    # Remove user data.
    if opts.remove_user_data:
        report(progress, pct=UNINSTALL_USER_DATA_PCT, message="Removing user data...")
        data_root = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        cache_root = Path(user_cache_dir(APP_NAME, APP_AUTHOR))
        shutil.rmtree(data_root, ignore_errors=True)
        shutil.rmtree(cache_root, ignore_errors=True)

    # Remove install directory.
    report(progress, pct=UNINSTALL_SCHEDULE_PCT, message="Scheduling file removal...")
    _schedule_delete_after_exit(install_dir)


def uninstall_with_feedback(
    identity,
    opts: UninstallOptions,
    *,
    progress=None,
    cancel_event=None,
) -> None:  # noqa: ANN001
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise InstallerOperationError("Cancelled")
    report(progress, pct=UNINSTALL_READ_PCT, message="Reading installation metadata...")
    uninstall(identity, opts, progress=progress)
    report(progress, pct=COMPLETE_PCT, message="Uninstall scheduled. Closing...")


def _schedule_delete_after_exit(install_dir: Path) -> None:
    """Schedule deletion of install_dir after this process exits.

    If uninstall is invoked from the installed installer copy, Windows will lock
    the running exe. Deleting the whole install directory is therefore done by a
    detached background process.
    """

    install_dir = install_dir.resolve()

    # Use PowerShell with a hidden window.
    # Avoid cmd.exe because it can flash a console window.
    escaped = str(install_dir).replace("'", "''")
    ps = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-Command",
        (
            "Start-Sleep -Seconds 2; "
            f"Remove-Item -LiteralPath '{escaped}' -Recurse -Force "
            "-ErrorAction SilentlyContinue"
        ),
    ]

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.Popen(  # noqa: S603
        ps,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=create_no_window | subprocess.DETACHED_PROCESS,
    )
