from __future__ import annotations

from pathlib import Path

from voice_reader.shared import single_instance


class _SigConnectRaises:
    def connect(self, _cb):  # noqa: ANN001
        raise RuntimeError("boom")


class _SigNoop:
    def connect(self, _cb):  # noqa: ANN001
        return


class _Server:
    def __init__(
        self, *, listen_ok: bool = True, pending=None, next_raises: bool = False
    ):  # noqa: ANN001
        self._listen_ok = listen_ok
        self._pending = pending
        self._next_raises = next_raises
        self.newConnection = _SigNoop()  # type: ignore[assignment]
        self.closed = False

    @staticmethod
    def removeServer(_name: str) -> bool:  # noqa: N802
        return True

    def listen(self, _name: str) -> bool:
        return bool(self._listen_ok)

    def close(self) -> None:
        self.closed = True

    def nextPendingConnection(self):  # noqa: ANN001
        if self._next_raises:
            raise RuntimeError("no")
        return self._pending


class _ServerRemoveRaises(_Server):
    @staticmethod
    def removeServer(_name: str) -> bool:  # noqa: N802
        raise RuntimeError("no")


class _Lock:
    def __init__(self, _path: str) -> None:
        self.unlocked = False

    def setStaleLockTime(self, _ms: int) -> None:  # noqa: N802
        return

    def tryLock(self, _timeout: int) -> bool:  # noqa: N802
        return True

    def unlock(self) -> None:
        self.unlocked = True


class _LockStaleRaises(_Lock):
    def setStaleLockTime(self, _ms: int) -> None:  # noqa: N802
        raise RuntimeError("no")


class _LockUnlockRaises(_Lock):
    def unlock(self) -> None:
        raise RuntimeError("no")


class _SockCloseRaises:
    def readAll(self):  # noqa: ANN001
        return b"ACTIVATE"

    def close(self) -> None:
        raise RuntimeError("no")


def _paths(tmp_path: Path) -> single_instance.SingleInstancePaths:
    return single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )


def test_paths_property_is_exposed(tmp_path: Path) -> None:
    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.paths.server_name == "s"


def test_try_become_primary_swallow_stale_lock_time_errors(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(single_instance, "QLockFile", _LockStaleRaises)
    monkeypatch.setattr(
        single_instance, "QLocalServer", lambda: _Server(listen_ok=True)
    )

    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.try_become_primary() is True


def test_try_become_primary_swallow_remove_server_errors(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(single_instance, "QLockFile", _Lock)
    monkeypatch.setattr(
        single_instance, "QLocalServer", lambda: _ServerRemoveRaises(listen_ok=True)
    )

    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.try_become_primary() is True


def test_try_become_primary_listen_failure_unlock_raises_is_swallowed(
    tmp_path: Path, monkeypatch
) -> None:
    lock = _LockUnlockRaises("x")

    def _lock_factory(_path: str) -> _LockUnlockRaises:
        return lock

    monkeypatch.setattr(single_instance, "QLockFile", _lock_factory)
    monkeypatch.setattr(
        single_instance, "QLocalServer", lambda: _Server(listen_ok=False)
    )

    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.try_become_primary() is True


def test_try_become_primary_connect_signal_errors_are_swallowed(
    tmp_path: Path, monkeypatch
) -> None:
    server = _Server(listen_ok=True)
    server.newConnection = _SigConnectRaises()  # type: ignore[assignment]

    monkeypatch.setattr(single_instance, "QLockFile", _Lock)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: server)

    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.try_become_primary() is True


def test_notify_primary_exception_returns_false_and_cleanup_swallowed(
    tmp_path: Path, monkeypatch
) -> None:
    class _Sock:
        def connectToServer(self, _name: str) -> None:
            raise RuntimeError("no")

        def disconnectFromServer(self) -> None:
            raise RuntimeError("no")

        def close(self) -> None:
            raise RuntimeError("no")

    monkeypatch.setattr(single_instance, "QLocalSocket", lambda: _Sock())
    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.notify_primary() is False


def test_notify_primary_disconnect_and_close_exceptions_are_swallowed(
    tmp_path: Path, monkeypatch
) -> None:
    class _Sock:
        def connectToServer(self, _name: str) -> None:
            return

        def waitForConnected(self, _ms: int) -> bool:  # noqa: N802
            return True

        def write(self, _payload: bytes) -> None:
            return

        def flush(self) -> None:
            return

        def waitForBytesWritten(self, _ms: int) -> bool:  # noqa: N802
            return True

        def disconnectFromServer(self) -> None:
            raise RuntimeError("no")

        def close(self) -> None:
            raise RuntimeError("no")

    monkeypatch.setattr(single_instance, "QLocalSocket", lambda: _Sock())
    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    assert g.notify_primary(payload=b"X") is True


def test_close_swallow_server_and_lock_exceptions(tmp_path: Path) -> None:
    class _BadServer:
        def close(self) -> None:
            raise RuntimeError("no")

    class _BadLock:
        def unlock(self) -> None:
            raise RuntimeError("no")

    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    g._server = _BadServer()  # noqa: SLF001
    g._lock = _BadLock()  # noqa: SLF001
    g.close()


def test_on_new_connection_returns_when_server_missing(tmp_path: Path) -> None:
    g = single_instance.SingleInstance(paths=_paths(tmp_path))
    g._on_new_connection()  # server is None


def test_on_new_connection_swallow_next_pending_errors_and_cb_errors(
    tmp_path: Path,
) -> None:
    called = {"n": 0}

    def _cb() -> None:
        called["n"] += 1
        raise RuntimeError("no")

    g = single_instance.SingleInstance(paths=_paths(tmp_path), on_activate=_cb)
    g._server = _Server(next_raises=True)  # noqa: SLF001
    g._on_new_connection()
    assert called["n"] == 1


def test_on_new_connection_swallow_socket_close_errors(tmp_path: Path) -> None:
    called = {"n": 0}

    def _cb() -> None:
        called["n"] += 1

    g = single_instance.SingleInstance(paths=_paths(tmp_path), on_activate=_cb)
    g._server = _Server(pending=_SockCloseRaises())  # noqa: SLF001
    g._on_new_connection()
    assert called["n"] == 1
