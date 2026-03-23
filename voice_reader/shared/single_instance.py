"""Single-instance guard + activation IPC.

Uses Qt primitives so it works consistently in GUI contexts:

- QLockFile: exclusivity (who is primary)
- QLocalServer/QLocalSocket: activation message to primary instance

This module intentionally lives in `voice_reader.shared` and must not import
other `voice_reader.*` layers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable

try:
    from PySide6.QtCore import QLockFile
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
except Exception:  # noqa: BLE001  # pragma: no cover
    # This is only hit in environments without PySide6/QtNetwork.
    QLocalServer = None  # type: ignore[assignment]  # pragma: no cover
    QLocalSocket = None  # type: ignore[assignment]  # pragma: no cover
    QLockFile = None  # type: ignore[assignment]  # pragma: no cover


def stable_server_name(*, namespace: str, lock_path: Path) -> str:
    """Create a stable per-app server name (safe for QLocalServer backends)."""

    h = hashlib.sha256(str(lock_path).encode("utf-8", errors="replace")).hexdigest()
    # Keep the name short-ish for Windows named-pipe backends.
    return f"{namespace}-{h[:16]}"


@dataclass(frozen=True, slots=True)
class SingleInstancePaths:
    lock_path: Path
    server_name: str


class SingleInstance:
    """Enforce single-instance and route activation requests to the primary."""

    def __init__(
        self,
        *,
        paths: SingleInstancePaths,
        on_activate: Callable[[], None] | None = None,
    ) -> None:
        self._paths = paths
        self._on_activate = on_activate

        self._lock = None
        self._server = None

    @property
    def paths(self) -> SingleInstancePaths:
        return self._paths

    def try_become_primary(self) -> bool:
        """Attempt to become the primary instance.

        Returns:
            True if this process is primary (lock acquired), else False.
        """

        if QLockFile is None or QLocalServer is None:
            # If QtNetwork isn't available, avoid blocking startup.
            return True

        self._paths.lock_path.parent.mkdir(parents=True, exist_ok=True)

        lock = QLockFile(str(self._paths.lock_path))

        # Best-effort: allow immediate stale lock cleanup.
        try:
            lock.setStaleLockTime(0)
        except Exception:
            pass

        if not bool(lock.tryLock(0)):
            return False

        self._lock = lock

        # Ensure any stale server name is removed (e.g., crash).
        try:
            QLocalServer.removeServer(self._paths.server_name)
        except Exception:
            pass

        server = QLocalServer()
        if not bool(server.listen(self._paths.server_name)):
            # If listen fails for any reason, release the lock and fall back
            # to "no single-instance enforcement" rather than deadlocking.
            try:
                lock.unlock()
            except Exception:
                pass
            self._lock = None
            return True

        self._server = server

        try:
            server.newConnection.connect(self._on_new_connection)
        except Exception:
            pass

        return True

    def notify_primary(
        self, *, payload: bytes = b"ACTIVATE", timeout_ms: int = 250
    ) -> bool:
        """Notify an already-running primary instance to activate.

        Returns:
            True if we likely delivered the message, else False.
        """

        if QLocalSocket is None:
            return False

        sock = QLocalSocket()
        try:
            sock.connectToServer(self._paths.server_name)
            if hasattr(sock, "waitForConnected") and not bool(
                sock.waitForConnected(int(timeout_ms))
            ):
                return False
            if hasattr(sock, "write"):
                sock.write(payload)
            if hasattr(sock, "flush"):
                sock.flush()
            if hasattr(sock, "waitForBytesWritten"):
                sock.waitForBytesWritten(int(timeout_ms))
            return True
        except Exception:
            return False
        finally:
            try:
                if hasattr(sock, "disconnectFromServer"):
                    sock.disconnectFromServer()
            except Exception:
                pass
            try:
                if hasattr(sock, "close"):
                    sock.close()
            except Exception:
                pass

    def close(self) -> None:
        """Release lock and stop server (best-effort)."""

        try:
            if self._server is not None:
                self._server.close()
        except Exception:
            pass
        self._server = None

        try:
            if self._lock is not None:
                self._lock.unlock()
        except Exception:
            pass
        self._lock = None

    def _on_new_connection(self) -> None:
        """Handle activation request from a secondary instance."""

        srv = self._server
        if srv is None:
            return

        try:
            sock = srv.nextPendingConnection()
        except Exception:
            sock = None

        # Always consume/close the socket to avoid resource leaks.
        try:
            if sock is not None and hasattr(sock, "readAll"):
                _ = sock.readAll()
        except Exception:
            pass
        finally:
            try:
                if sock is not None and hasattr(sock, "close"):
                    sock.close()
            except Exception:
                pass

        cb = self._on_activate
        if cb is None:
            return
        try:
            cb()
        except Exception:
            return


def _touch() -> None:
    """Coverage helper for import-guarded environments."""

    return
