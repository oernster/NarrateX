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

