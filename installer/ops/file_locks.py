"""Writing a file another program still has open.

Measured on 2026-09-17: a repair retried 5.3 seconds after NarrateX was closed
passed the running-app check, then failed 84ms later opening NarrateX.exe for
writing with PermissionError 13. The process list alone does not prove a file
is free: something else can hold it open for a while (the holder that time was
not recorded). So a write that meets a lock waits a bounded time for it to be
released and records who holds it. When it stays locked, the failure names the
file and the holder in words rather than surfacing a raw PermissionError.

The holders come from the Windows Restart Manager, which reports every process
with the file open. Anywhere it cannot answer, the holders are simply unknown.
"""

from __future__ import annotations

import ctypes
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from installer.ops.errors import InstallerOperationError

# How long a write waits for a lock to clear; how often it tries again.
FILE_LOCK_WAIT_SECONDS = 10.0
FILE_LOCK_POLL_SECONDS = 0.25

# Restart Manager buffer sizes, from RestartManager.h.
_CCH_RM_SESSION_KEY = 32
_CCH_RM_MAX_APP_NAME = 255
_CCH_RM_MAX_SVC_NAME = 63
_ERROR_SUCCESS = 0

_log = logging.getLogger("installer.file_locks")


class FileInUseError(InstallerOperationError):
    """A file stayed open in another program for the whole wait."""


def lock_holders(path: Path) -> tuple[str, ...]:
    """Each process holding `path` open, as "Name (pid N)"; empty when unknown."""

    if os.name != "nt":
        return ()
    try:
        return _restart_manager_holders(path)
    except Exception:  # noqa: BLE001
        # Degrades to naming nobody. The holders are a diagnosis for the
        # message and the log; failing to read them must never turn a
        # recoverable lock into a different failure.
        _log.exception("Could not ask Windows who holds %s", path)
        return ()


def open_for_write(
    path: Path,
    *,
    on_wait: Callable[[tuple[str, ...]], None] | None = None,
    wait_seconds: float = FILE_LOCK_WAIT_SECONDS,
    poll_seconds: float = FILE_LOCK_POLL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> BinaryIO:
    """Open `path` for writing, waiting a bounded time for a lock to clear."""

    deadline = clock() + wait_seconds
    while True:
        try:
            return path.open("wb")
        except PermissionError:
            holders = lock_holders(path)
            _log.warning("%s is locked; held by %s", path, holders or "unknown")
            if clock() >= deadline:
                raise FileInUseError(_in_use_message(path, holders)) from None
            if on_wait is not None:
                on_wait(holders)
            sleep(poll_seconds)


def _in_use_message(path: Path, holders: tuple[str, ...]) -> str:
    by = (
        ", ".join(holders) if holders else "another program (Windows did not say which)"
    )
    return (
        f"{path.name} could not be written because it is in use by {by}. "
        "Close that program, then try again."
    )


def _restart_manager_holders(path: Path) -> tuple[str, ...]:
    from ctypes import wintypes

    class _UniqueProcess(ctypes.Structure):
        _fields_ = [
            ("dwProcessId", wintypes.DWORD),
            ("ProcessStartTime", wintypes.FILETIME),
        ]

    class _ProcessInfo(ctypes.Structure):
        _fields_ = [
            ("Process", _UniqueProcess),
            ("strAppName", wintypes.WCHAR * (_CCH_RM_MAX_APP_NAME + 1)),
            ("strServiceShortName", wintypes.WCHAR * (_CCH_RM_MAX_SVC_NAME + 1)),
            ("ApplicationType", wintypes.DWORD),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.DWORD),
            ("bRestartable", wintypes.BOOL),
        ]

    rm = ctypes.WinDLL("rstrtmgr")
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(_CCH_RM_SESSION_KEY + 1)
    if rm.RmStartSession(ctypes.byref(session), 0, key) != _ERROR_SUCCESS:
        return ()
    try:
        files = (wintypes.LPCWSTR * 1)(str(path))
        if (
            rm.RmRegisterResources(session, 1, files, 0, None, 0, None)
            != _ERROR_SUCCESS
        ):
            return ()
        needed = wintypes.UINT()
        count = wintypes.UINT(0)
        reason = wintypes.UINT()
        # The first call only sizes the list; the second fills it.
        rm.RmGetList(
            session,
            ctypes.byref(needed),
            ctypes.byref(count),
            None,
            ctypes.byref(reason),
        )
        if needed.value == 0:
            return ()
        infos = (_ProcessInfo * needed.value)()
        count = wintypes.UINT(needed.value)
        if (
            rm.RmGetList(
                session,
                ctypes.byref(needed),
                ctypes.byref(count),
                infos,
                ctypes.byref(reason),
            )
            != _ERROR_SUCCESS
        ):
            return ()
        return tuple(
            f"{infos[i].strAppName} (pid {infos[i].Process.dwProcessId})"
            for i in range(count.value)
        )
    finally:
        rm.RmEndSession(session)
