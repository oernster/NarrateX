"""Windows-specific integration helpers.

This module is intentionally safe to import on non-Windows platforms.
"""

from __future__ import annotations

import os


def set_app_user_model_id(app_id: str) -> None:
    """Set the Windows AppUserModelID for correct taskbar/pinned icon identity.

    On Windows, the AppUserModelID affects taskbar grouping and which icon is
    used for a running process vs. a pinned shortcut.

    Must be called early in process startup (before creating the first window).
    """

    if not app_id:
        return

    if os.name != "nt":
        return

    # Avoid importing ctypes at module import time for non-Windows.
    try:
        import ctypes  # noqa: WPS433 (stdlib)

        # https://learn.microsoft.com/windows/win32/api/shellapi/nf-shellapi-setcurrentprocessexplicitappusermodelid
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        # Best-effort only; failing to set this should not prevent startup.
        return
