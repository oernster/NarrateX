"""UI startup helpers.

These functions live in `voice_reader.shared` so they can be used by the app
entrypoint without importing higher layers.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
from typing import Any, Callable

from voice_reader.shared.resources import find_splash_image_path
from voice_reader.shared.single_instance import (
    SingleInstance,
    SingleInstancePaths,
    stable_server_name,
)


def is_mp_child_process() -> bool:
    """Best-effort detection for multiprocessing child processes."""

    try:
        return mp.parent_process() is not None
    except Exception:
        return False


def is_real_pyside_app(app: object) -> bool:
    """Heuristic: tests often replace QApplication with fakes."""

    try:
        return app.__class__.__module__.startswith("PySide6")
    except Exception:
        return False  # pragma: no cover


def _touch() -> None:
    """Coverage helper."""

    return


def activate_window(window: object) -> None:
    """Best-effort raise/focus for an existing main window."""

    for method_name in ("showNormal", "raise_", "activateWindow"):
        try:
            fn = getattr(window, method_name, None)
            if callable(fn):
                fn()
        except Exception:
            continue


def setup_single_instance(
    *,
    app: object,
    app_id: str,
    allow_multi: bool,
    lock_dir: Path,
    on_activate: Callable[[], None],
) -> tuple[SingleInstance | None, bool]:
    """Return (guard, is_primary)."""

    if allow_multi or is_mp_child_process() or (not is_real_pyside_app(app)):
        return None, True

    lock_path = lock_dir / "single_instance.lock"
    paths = SingleInstancePaths(
        lock_path=lock_path,
        server_name=stable_server_name(namespace=app_id, lock_path=lock_path),
    )
    guard = SingleInstance(paths=paths, on_activate=on_activate)
    is_primary = bool(guard.try_become_primary())
    return guard, is_primary


def maybe_show_splash(
    *,
    app: object,
    icon: Any,
    project_root: Path,
    enabled: bool,
) -> object | None:
    """Show splash screen (best-effort). Returns the splash object or None."""

    if not enabled or (not is_real_pyside_app(app)):
        return None

    try:
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QSplashScreen
    except Exception:
        return None

    try:
        splash_path = find_splash_image_path(project_root=project_root)
        if splash_path is None:
            return None
        pm = QPixmap(str(splash_path))
        if pm.isNull():
            return None
        splash = QSplashScreen(pm)

        # Icon is best-effort.
        try:
            splash.setWindowIcon(icon)
        except Exception:
            pass

        splash.show()

        # Ensure it paints before heavy imports/initialization.
        try:
            getattr(app, "processEvents", lambda: None)()
        except Exception:  # pragma: no cover
            pass
        return splash
    except Exception:
        return None  # pragma: no cover


def default_lock_dir(*, app_name: str) -> Path:
    """Choose a stable per-user location for locks.

    Prefer TEMP; it exists on Windows and is user-scoped.
    """

    tmp = os.getenv("TEMP", "").strip()
    base = Path(tmp) if tmp else Path.cwd()
    return base / app_name

