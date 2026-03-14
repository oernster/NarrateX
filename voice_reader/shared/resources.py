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

    # In onedir PyInstaller builds, user-added data files can end up under
    # `_internal/` depending on how the `.spec` is generated.
    try:
        candidates.append(
            Path(sys.executable).resolve().parent / "_internal" / "narratex.ico"
        )
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

        # In onedir PyInstaller builds, user-added data files can end up under
        # `_internal/` depending on how the `.spec` is generated.
        try:
            exe_dir = Path(sys.executable).resolve().parent
            roots.append(exe_dir / "_internal")
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


def iter_qt_window_icon_candidates(*, project_root: Path | None = None) -> list[Path]:
    """Return icon file candidates (in preference order) for Qt window/taskbar icons.

    This does *not* require Qt and only checks for file existence.

    The caller should still verify the icon is actually loadable by Qt
    (e.g. `.ico` may exist but fail to load if the Qt ICO plugin is missing).
    """

    def _roots() -> list[Path]:
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

        # Repo layout fallback.
        try:
            roots.append(Path(__file__).resolve().parents[2])
        except Exception:
            pass

        # CWD.
        try:
            roots.append(Path.cwd())
        except Exception:
            pass

        # De-dup while preserving order.
        seen: set[str] = set()
        out: list[Path] = []
        for r in roots:
            key = str(r)
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    filenames = [
        # Prefer native ICO, then fall back to PNGs.
        "narratex.ico",
        "narratex_256.png",
        "narratex_128.png",
        "narratex_64.png",
        "narratex_48.png",
        "narratex_32.png",
        "narratex_16.png",
    ]

    candidates: list[Path] = []
    roots = _roots()

    # In onedir PyInstaller builds, user-added data files can end up under
    # `_internal/` depending on how the `.spec` is generated.
    internal_roots: list[Path] = []
    for r in list(roots):
        try:
            internal_roots.append(r / "_internal")
        except Exception:
            continue

    for root in roots + internal_roots:
        for name in filenames:
            p = root / name
            try:
                if p.exists() and p.is_file():
                    candidates.append(p)
            except Exception:
                continue

    # De-dup while preserving order.
    seen2: set[str] = set()
    out2: list[Path] = []
    for p in candidates:
        key = str(p)
        if key in seen2:
            continue
        seen2.add(key)
        out2.append(p)
    return out2
