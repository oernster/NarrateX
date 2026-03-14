"""Create/remove per-user shortcuts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from installer.constants import InstallerIdentity


@dataclass(frozen=True, slots=True)
class ShortcutPaths:
    desktop_lnk: Path
    start_menu_lnk: Path


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Shortcuts are supported on Windows only")


def get_shortcut_paths(identity: InstallerIdentity) -> ShortcutPaths:
    _require_windows()

    # Per-user Desktop.
    desktop_dir = Path(os.path.join(os.path.expanduser("~"), "Desktop"))

    # Per-user Start Menu Programs.
    appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    programs_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    start_menu_folder = programs_dir / identity.start_menu_folder

    return ShortcutPaths(
        desktop_lnk=desktop_dir / f"{identity.shortcut_name}.lnk",
        start_menu_lnk=start_menu_folder / f"{identity.shortcut_name}.lnk",
    )


def create_shortcut(target_exe: Path, shortcut_path: Path, *, working_dir: Path | None = None) -> None:
    _require_windows()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    # Use WScript.Shell COM automation.
    import win32com.client  # type: ignore  # noqa: WPS433

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))
    shortcut.TargetPath = str(target_exe)
    if working_dir is not None:
        shortcut.WorkingDirectory = str(working_dir)
    shortcut.IconLocation = str(target_exe)
    shortcut.Save()


def remove_shortcut(shortcut_path: Path) -> None:
    try:
        shortcut_path.unlink(missing_ok=True)
    except Exception:
        # Best effort.
        return

    # Remove parent folder if empty (Start Menu subfolder).
    try:
        if shortcut_path.parent.exists() and not any(shortcut_path.parent.iterdir()):
            shortcut_path.parent.rmdir()
    except Exception:
        return

