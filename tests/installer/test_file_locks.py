"""A write that meets a lock waits for it, then names the holder.

The lock here is real: the test holds the file open with no sharing allowed,
which is exactly the PermissionError 13 a repair met on NarrateX.exe.
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

import pytest

from installer.ops import file_locks
from installer.ops.file_locks import FileInUseError, lock_holders, open_for_write

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows file locking")

_GENERIC_READ = 0x80000000
_NO_SHARING = 0
_OPEN_EXISTING = 3
_NORMAL = 0x80
_SHORT_WAIT_SECONDS = 0.3
_RELEASE_AFTER_SECONDS = 0.3
_LONG_WAIT_SECONDS = 5.0
_FAST_POLL_SECONDS = 0.02

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
if _kernel32 is not None:
    _kernel32.CreateFileW.restype = wintypes.HANDLE


def _lock(path):
    handle = _kernel32.CreateFileW(
        str(path), _GENERIC_READ, _NO_SHARING, None, _OPEN_EXISTING, _NORMAL, None
    )
    assert handle not in (None, wintypes.HANDLE(-1).value)
    return handle


def test_holders_name_this_process_only_while_it_holds_the_file(tmp_path) -> None:
    target = tmp_path / "NarrateX.exe"
    target.write_bytes(b"old")
    assert lock_holders(target) == ()
    handle = _lock(target)
    try:
        assert any(f"(pid {os.getpid()})" in h for h in lock_holders(target))
    finally:
        _kernel32.CloseHandle(handle)
    assert lock_holders(target) == ()


def test_a_lock_released_during_the_wait_lets_the_write_through(tmp_path) -> None:
    target = tmp_path / "NarrateX.exe"
    target.write_bytes(b"old")
    handle = _lock(target)
    waits: list = []
    release = threading.Timer(_RELEASE_AFTER_SECONDS, _kernel32.CloseHandle, [handle])
    release.start()
    try:
        with open_for_write(
            target,
            on_wait=waits.append,
            wait_seconds=_LONG_WAIT_SECONDS,
            poll_seconds=_FAST_POLL_SECONDS,
        ) as out:
            out.write(b"new")
    finally:
        release.join()
    assert target.read_bytes() == b"new"
    assert waits, "the write should have met the lock and waited"


def test_a_lock_that_outlasts_the_wait_is_named(tmp_path) -> None:
    target = tmp_path / "NarrateX.exe"
    target.write_bytes(b"old")
    handle = _lock(target)
    try:
        with pytest.raises(FileInUseError) as caught:
            open_for_write(
                target,
                wait_seconds=_SHORT_WAIT_SECONDS,
                poll_seconds=_FAST_POLL_SECONDS,
            )
    finally:
        _kernel32.CloseHandle(handle)
    message = str(caught.value)
    assert "NarrateX.exe" in message
    assert f"(pid {os.getpid()})" in message
    assert target.read_bytes() == b"old"


def test_unknown_holders_are_said_to_be_unknown(tmp_path, monkeypatch) -> None:
    target = tmp_path / "NarrateX.exe"
    target.write_bytes(b"old")
    monkeypatch.setattr(file_locks, "lock_holders", lambda path: ())
    handle = _lock(target)
    try:
        with pytest.raises(FileInUseError, match="did not say which"):
            open_for_write(target, wait_seconds=0, poll_seconds=_FAST_POLL_SECONDS)
    finally:
        _kernel32.CloseHandle(handle)
