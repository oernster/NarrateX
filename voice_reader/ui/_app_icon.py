"""Application icon and platform identity helpers for the startup entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from voice_reader.version import APP_APPUSERMODELID

# Shipped PNG sizes (must match buildexe.py add_data list).
_ICON_PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)


def exe_dir() -> Path:
    """Return directory containing the executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def set_windows_app_identity() -> None:
    """Ensure Windows groups the app correctly in the taskbar."""
    if os.name != "nt":
        return
    try:
        import ctypes  # noqa: WPS433

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_APPUSERMODELID
        )
    except Exception:
        pass


def build_runtime_icon() -> QIcon:
    """Build multi-resolution QIcon from shipped PNGs (avoids ICO decode failures in frozen builds)."""
    base = exe_dir()
    icon = QIcon()
    for size in _ICON_PNG_SIZES:
        candidate = base / f"narratex_{size}.png"
        if candidate.exists():
            icon.addFile(str(candidate), QSize(size, size))
    return icon
