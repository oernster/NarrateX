"""Runtime helpers for the packaged Windows build.

This module supports the distribution layout:

- dist/NarrateX.exe
- dist/ext/                     (optional: external Python packages)
- dist/hf-cache/                (optional: pre-downloaded HuggingFace assets)

It keeps the *EXE* smaller by allowing heavy dependencies to live next to the
executable rather than being embedded in the onefile payload.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _exe_dir() -> Path:
    """Best-effort folder containing the *distribution root*.

    In some packaged builds, `sys.executable` may point at an embedded
    interpreter/runtime rather than the launcher EXE, while the real entry
    executable path is `sys.argv[0]` (e.g. `.../NarrateX.exe`).

    For our distribution layout we want the folder that contains:
    - NarrateX.exe
    - ext/
    - hf-cache/
    """

    # Prefer argv[0] when it looks like the actual app executable.
    try:
        argv0 = Path(sys.argv[0]).resolve()
        if argv0.suffix.lower() == ".exe" and argv0.exists():
            return argv0.parent
    except Exception:
        pass

    # Fallback: Python interpreter location.
    try:
        exe = Path(sys.executable).resolve()
    except Exception:
        exe = Path.cwd()
    return exe.parent


def add_external_site_packages(*, ext_dir_name: str = "ext") -> Path | None:
    """Prepend a sibling `ext/` folder to sys.path.

    Returns the inserted path (if any).
    """

    base = _exe_dir()
    ext_dir = base / ext_dir_name
    if not ext_dir.exists() or not ext_dir.is_dir():
        return None

    # Put it first, so external wheels take precedence over embedded modules.
    ext_str = str(ext_dir)
    if ext_str not in sys.path:
        sys.path.insert(0, ext_str)

    # Help Windows locate DLLs shipped in ext/ (e.g. torch/lib/*.dll,
    # _soundfile_data/*.dll). This is required on Python 3.8+ where the default
    # DLL search path is more restrictive.
    try:
        os.add_dll_directory(ext_str)  # type: ignore[attr-defined]
    except Exception:
        pass

    for dll_subdir in [
        ext_dir / "torch" / "lib",
        ext_dir / "_soundfile_data",
        ext_dir / "_sounddevice_data" / "portaudio-binaries",
    ]:
        try:
            if dll_subdir.exists() and dll_subdir.is_dir():
                os.add_dll_directory(str(dll_subdir))  # type: ignore[attr-defined]
        except Exception:
            pass
    return ext_dir


def configure_huggingface_cache(*, cache_dir_name: str = "hf-cache") -> Path | None:
    """Point HF/Transformers caches at a sibling folder.

    This makes offline/cold-start runs possible when assets were pre-downloaded
    during the build step.

    Returns the configured cache dir (if any).
    """

    base = _exe_dir()
    cache_dir = base / cache_dir_name
    if not cache_dir.exists() or not cache_dir.is_dir():
        return None

    # huggingface_hub uses HF_HOME/HF_HUB_CACHE; transformers uses
    # TRANSFORMERS_CACHE or HF_HOME.
    cache_str = str(cache_dir)
    os.environ.setdefault("HF_HOME", cache_str)
    os.environ.setdefault("HF_HUB_CACHE", cache_str)
    os.environ.setdefault("TRANSFORMERS_CACHE", cache_str)
    return cache_dir


def configure_packaged_runtime() -> None:
    """Configure sys.path + caches for the packaged build.

    Safe to call in dev mode; it becomes a no-op if folders are absent.
    """

    add_external_site_packages()
    configure_huggingface_cache()
