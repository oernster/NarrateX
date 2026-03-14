"""Qt icon helpers.

We intentionally render a simple emoji window icon for the installer runtime.

Rationale
---------
On Windows, the caption icon (top-left of the window chrome) is always rendered
at a very small size (effectively ~16x16). Even a correctly multi-resolution
`.ico` can be hard to identify there.

Using an emoji (🎤) makes the caption icon recognizable at tiny sizes.
Note: Windows often uses the window icon for the running taskbar button icon as
well; the embedded exe icon still controls Explorer/Start Menu/shortcut icons.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import os
import sys
from pathlib import Path

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtGui import QIcon


def render_emoji_icon(
    emoji: str,
    *,
    sizes: Iterable[int] = (16, 20, 24, 32, 48, 64),
    font_families: Sequence[str] = ("Segoe UI Emoji", "Segoe UI Symbol"),
) -> QIcon:
    """Render an emoji into a multi-size :class:`~PySide6.QtGui.QIcon`.

    This must be called after a QApplication is created (because it uses
    QPixmap/QPainter).
    """

    # Local import keeps this module importable in non-Qt contexts.
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap

    icon = QIcon()

    try:
        available = set(QFontDatabase.families())
    except Exception:
        available = set()

    chosen_family: str | None = None
    for fam in font_families:
        if fam in available:
            chosen_family = fam
            break

    for size in sizes:
        try:
            px = int(size)
            if px <= 0:
                continue

            pixmap = QPixmap(px, px)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            try:
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.TextAntialiasing, True)

                font = QFont()
                if chosen_family:
                    font.setFamily(chosen_family)

                # Slightly smaller than the pixmap to avoid clipping.
                font.setPixelSize(max(10, int(px * 0.82)))
                painter.setFont(font)

                painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
            finally:
                painter.end()

            icon.addPixmap(pixmap)
        except Exception:
            # Best-effort: if a given size fails, try the next.
            continue

    return icon


def build_installer_window_icon(*, project_root: Path) -> QIcon:
    """Build the installer runtime window icon.

    Desired behavior:
    - Caption icon (tiny) + taskbar button icon: use 🎤 so it's recognizable.

    Note: when running the installer from source (`python -m installer.app`),
    Windows may still show the Python icon in the taskbar due to process
    grouping. The frozen `NarrateXSetup.exe` build should use the embedded exe
    icon and/or the larger pixmaps we add to this QIcon.
    """

    # Prefer emoji for *all* runtime surfaces while the installer is running.
    # If emoji rendering fails (missing font/plugin), fall back to the branded
    # icon files.
    emoji_icon = render_emoji_icon("🎤", sizes=(16, 20, 24, 32, 48, 64))
    if not emoji_icon.isNull():
        return emoji_icon

    from PySide6.QtGui import QIcon

    brand_path = _find_brand_icon_path(project_root=project_root)
    if brand_path is not None:
        return QIcon(str(brand_path))

    return QIcon()


def _find_brand_icon_path(*, project_root: Path) -> Path | None:
    """Find a branded icon file for the installer runtime window icon.

    Prefer PNGs (we have a known-good multi-size PNG set), then fall back to the
    `.ico` if needed.
    """

    filenames = [
        "narratex_256.png",
        "narratex_128.png",
        "narratex_64.png",
        "narratex_48.png",
        "narratex.ico",
    ]

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

    for root in roots:
        for name in filenames:
            p = root / name
            try:
                if p.exists() and p.is_file():
                    return p
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
