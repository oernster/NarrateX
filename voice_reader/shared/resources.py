"""Runtime resource discovery.

For packaging (e.g., Nuitka onefile), we want a robust way to locate bundled
assets without hard-coding absolute paths.
"""

from __future__ import annotations

import sys
from pathlib import Path


def find_app_icon_path(*, project_root: Path | None = None) -> Path | None:
    """Locate the NarrateX `.ico` file for runtime window/taskbar icons."""

    candidates: list[Path] = []

    # PyInstaller onefile extracts bundled data files to sys._MEIPASS.
    # If we ship narratex.ico as an --add-data, it will be available here.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "narratex.ico")
    except Exception:
        pass

    if project_root is not None:
        candidates.append(project_root / "narratex.ico")

    # When packaged, placing narratex.ico next to the exe is a common pattern.
    try:
        candidates.append(Path(sys.executable).resolve().parent / "narratex.ico")
    except Exception:
        pass

    # Repo layout fallback: voice_reader/shared/resources.py -> repo root is parents[2].
    try:
        candidates.append(Path(__file__).resolve().parents[2] / "narratex.ico")
    except Exception:
        pass

    # As a final fallback, look in CWD.
    candidates.append(Path.cwd() / "narratex.ico")

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue

    return None


def find_qt_window_icon_path(*, project_root: Path | None = None) -> Path | None:
    """Locate an icon file suitable for Qt window/taskbar icons.

    Prefer `.ico` (native Windows icon), but fall back to a bundled `.png` if
    the Qt ICO plugin is unavailable in the frozen build.
    """

    def _candidate_roots() -> list[Path]:
        roots: list[Path] = []

        if project_root is not None:
            roots.append(project_root)

        # PyInstaller onefile extracts bundled data files to sys._MEIPASS.
        try:
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                roots.append(Path(meipass))
        except Exception:
            pass

        # Next to exe.
        try:
            roots.append(Path(sys.executable).resolve().parent)
        except Exception:
            pass

        # Repo layout fallback: voice_reader/shared/resources.py -> repo root is parents[2].
        try:
            roots.append(Path(__file__).resolve().parents[2])
        except Exception:
            pass

        # As a final fallback, look in CWD.
        roots.append(Path.cwd())
        return roots

    filenames = [
        "narratex.ico",
        "narratex_256.png",
        "narratex_128.png",
        "narratex_64.png",
        "narratex_48.png",
        "narratex_32.png",
        "narratex_16.png",
    ]

    for root in _candidate_roots():
        for name in filenames:
            p = root / name
            try:
                if p.exists() and p.is_file():
                    return p
            except Exception:
                continue

    return None

