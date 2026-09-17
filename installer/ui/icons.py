"""Qt icon helpers.

The installer's window wears the NarrateX mark, the same one the application,
its shortcuts and the site carry, so the setup program reads as the same
product. Every size `generate_icons.py` emits is added to one QIcon, so the
tiny caption icon gets the frame reduced for that size straight from the
master rather than a large frame squeezed down by Qt.

Note: Windows often uses the window icon for the running taskbar button icon as
well; the embedded exe icon still controls Explorer/Start Menu/shortcut icons.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import os
import sys
from pathlib import Path

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtGui import QIcon

# The derived sizes staged beside the installer, smallest first, then the
# Windows icon as the last resort.
BRAND_PNG_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
BRAND_ICO = "narratex.ico"


def brand_png_name(size: int) -> str:
    return f"narratex_{size}.png"


def build_installer_window_icon(*, project_root: Path) -> QIcon:
    """The NarrateX mark at every staged size; a null icon when none is found.

    This must be called after a QApplication is created.
    """

    from PySide6.QtGui import QIcon

    icon = QIcon()
    for size in BRAND_PNG_SIZES:
        path = _find_brand_file(brand_png_name(size), project_root=project_root)
        if path is not None:
            icon.addFile(str(path))
    if not icon.isNull():
        return icon

    ico = _find_brand_file(BRAND_ICO, project_root=project_root)
    return QIcon(str(ico)) if ico is not None else QIcon()


def _candidate_roots(*, project_root: Path) -> list[Path]:
    roots: list[Path] = []

    # In a frozen PyInstaller build, bundled files live under sys._MEIPASS.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    except Exception:
        pass

    roots.append(project_root)

    # Next to exe.
    try:
        roots.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    # CWD as a final fallback.
    try:
        roots.append(Path.cwd())
    except Exception:
        pass

    return roots


def _find_brand_file(name: str, *, project_root: Path) -> Path | None:
    for root in _candidate_roots(project_root=project_root):
        path = root / name
        try:
            if path.is_file():
                return path
        except Exception:
            continue
    return None


def set_windows_app_user_model_id(app_id: str) -> None:
    """Set the Windows AppUserModelID for correct taskbar grouping/icon.

    This is a best-effort helper; it no-ops on non-Windows.
    """

    if os.name != "nt":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        return
