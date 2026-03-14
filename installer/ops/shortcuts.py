"""Create/remove per-user shortcuts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from installer.constants import InstallerIdentity
from voice_reader.version import APP_APPUSERMODELID


def _default_icon_location_for(target_exe: Path) -> str:
    """Choose the best icon source for a shortcut.

    Prefer `narratex.ico` next to the exe (deployed by the installer) so the
    shortcut uses the branded icon even if the exe's embedded icon changes.
    """

    try:
        ico = target_exe.resolve().parent / "narratex.ico"
        if ico.exists() and ico.is_file():
            return str(ico)
    except Exception:
        pass

    return str(target_exe)


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

    # Use a branded ICO file if available.
    shortcut.IconLocation = _default_icon_location_for(target_exe)

    # Ensure the shortcut has the same AppUserModelID as the running process.
    # This avoids Windows falling back to generic icons/grouping for the running
    # taskbar button when launched from this shortcut.
    _try_set_shortcut_app_user_model_id(shortcut, APP_APPUSERMODELID)

    shortcut.Save()


def _try_set_shortcut_app_user_model_id(shortcut, app_id: str) -> None:  # noqa: ANN001
    """Best-effort: stamp System.AppUserModel.ID onto a .lnk shortcut.

    Uses IShellLink + IPropertyStore via pywin32. If this fails, we still keep
    the shortcut functional.
    """

    if not app_id:
        return

    try:
        import pythoncom  # type: ignore  # noqa: WPS433
        from win32com.propsys import propsys  # type: ignore  # noqa: WPS433
        from win32com.shell import shell  # type: ignore  # noqa: WPS433
    except Exception:
        return

    try:
        # Convert the WScript.Shell shortcut COM object to IShellLink.
        link = shortcut.QueryInterface(shell.IID_IShellLink)
        store = link.QueryInterface(propsys.IID_IPropertyStore)

        key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
        pv = propsys.PROPVARIANTType(app_id)
        store.SetValue(key, pv)
        store.Commit()
    except Exception:
        return


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

