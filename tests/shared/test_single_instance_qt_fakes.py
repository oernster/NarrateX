from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.shared import single_instance


class _Sig:
    def __init__(self) -> None:
        self._cb = None

    def connect(self, cb):  # noqa: ANN001
        self._cb = cb

    def emit(self) -> None:
        if self._cb is not None:
            self._cb()


class _FakeLock:
    def __init__(self, path: str) -> None:
        self.path = path
        self.unlocked = False
        self.stale_time_set = False

    def setStaleLockTime(self, _ms: int) -> None:  # noqa: N802
        self.stale_time_set = True

    def tryLock(self, _timeout: int) -> bool:  # noqa: N802
        return True

    def unlock(self) -> None:
        self.unlocked = True


class _FakeLockTryFail(_FakeLock):
    def tryLock(self, _timeout: int) -> bool:  # noqa: N802
        return False


class _FakeServer:
    def __init__(self, *, listen_ok: bool) -> None:
        self.listen_ok = listen_ok
        self.newConnection = _Sig()
        self.closed = False
        self._pending = None  # type: ignore[assignment]

    @staticmethod
    def removeServer(_name: str) -> bool:  # noqa: N802
        return True

    def listen(self, _name: str) -> bool:
        return bool(self.listen_ok)

    def close(self) -> None:
        self.closed = True

    def nextPendingConnection(self):  # noqa: ANN001
        return self._pending


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False
        self.disconnected = False
        self.connected_to = None
        self.written: list[bytes] = []
        self.fail_connect = False
        self.wait_ok = True

    def connectToServer(self, name: str) -> None:
        if self.fail_connect:
            raise RuntimeError("no")
        self.connected_to = name

    def waitForConnected(self, _ms: int) -> bool:  # noqa: N802
        return bool(self.wait_ok)

    def write(self, payload: bytes) -> None:
        self.written.append(payload)

    def flush(self) -> None:
        return

    def waitForBytesWritten(self, _ms: int) -> bool:  # noqa: N802
        return True

    def disconnectFromServer(self) -> None:
        self.disconnected = True

    def close(self) -> None:
        self.closed = True

    def readAll(self):  # noqa: ANN001
        return b"ACTIVATE"


def test_try_become_primary_no_qt_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(single_instance, "QLockFile", None)
    monkeypatch.setattr(single_instance, "QLocalServer", None)
    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "x.lock", server_name="s"
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.try_become_primary() is True


def test_notify_primary_no_socket_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(single_instance, "QLocalSocket", None)
    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "x.lock", server_name="s"
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.notify_primary() is False


def test_try_become_primary_lock_contention_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(single_instance, "QLockFile", _FakeLockTryFail)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: _FakeServer(listen_ok=True))
    monkeypatch.setattr(single_instance, "QLocalSocket", _FakeSocket)

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.try_become_primary() is False


def test_try_become_primary_listen_failure_unlocks_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = _FakeLock("x")

    def _lock_factory(path: str) -> _FakeLock:
        del path
        return lock

    monkeypatch.setattr(single_instance, "QLockFile", _lock_factory)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: _FakeServer(listen_ok=False))

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.try_become_primary() is True
    assert lock.unlocked is True


def test_try_become_primary_sets_stale_lock_time_when_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = _FakeLock("x")

    def _lock_factory(path: str) -> _FakeLock:
        del path
        return lock

    monkeypatch.setattr(single_instance, "QLockFile", _lock_factory)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: _FakeServer(listen_ok=True))

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.try_become_primary() is True
    assert lock.stale_time_set is True


def test_on_new_connection_without_callback_is_noop(tmp_path: Path, monkeypatch) -> None:
    server = _FakeServer(listen_ok=True)
    server._pending = _FakeSocket()
    monkeypatch.setattr(single_instance, "QLockFile", _FakeLock)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: server)

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths, on_activate=None)
    assert g.try_become_primary() is True
    server.newConnection.emit()


def test_on_new_connection_swallow_socket_read_errors(tmp_path: Path, monkeypatch) -> None:
    server = _FakeServer(listen_ok=True)

    class _BadSock(_FakeSocket):
        def readAll(self):  # noqa: ANN001
            raise RuntimeError("boom")

    server._pending = _BadSock()

    monkeypatch.setattr(single_instance, "QLockFile", _FakeLock)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: server)

    called = {"n": 0}

    def _cb() -> None:
        called["n"] += 1

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths, on_activate=_cb)
    assert g.try_become_primary() is True
    server.newConnection.emit()
    assert called["n"] == 1


def test_close_closes_server_and_unlocks(tmp_path: Path, monkeypatch) -> None:
    server = _FakeServer(listen_ok=True)
    lock = _FakeLock("x")

    def _lock_factory(path: str) -> _FakeLock:
        del path
        return lock

    monkeypatch.setattr(single_instance, "QLockFile", _lock_factory)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: server)

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.try_become_primary() is True
    g.close()
    assert server.closed is True
    assert lock.unlocked is True


def test_primary_server_receives_activation_and_calls_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = _FakeServer(listen_ok=True)

    monkeypatch.setattr(single_instance, "QLockFile", _FakeLock)
    monkeypatch.setattr(single_instance, "QLocalServer", lambda: server)

    activated = {"n": 0}

    def _on_activate() -> None:
        activated["n"] += 1

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "NarrateX" / "single_instance.lock",
        server_name="s",
    )
    g = single_instance.SingleInstance(paths=paths, on_activate=_on_activate)
    assert g.try_become_primary() is True

    sock = _FakeSocket()
    server._pending = sock
    server.newConnection.emit()
    assert activated["n"] == 1
    assert sock.closed is True


def test_notify_primary_sends_payload_and_closes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = _FakeSocket()

    class _SockFactory:
        def __call__(self):
            return sock

    monkeypatch.setattr(single_instance, "QLocalSocket", _SockFactory())

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "x.lock",
        server_name="server",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.notify_primary(payload=b"ACTIVATE") is True
    assert sock.connected_to == "server"
    assert sock.written == [b"ACTIVATE"]
    assert sock.disconnected is True
    assert sock.closed is True


def test_notify_primary_connect_timeout_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sock = _FakeSocket()
    sock.wait_ok = False

    class _SockFactory:
        def __call__(self):
            return sock

    monkeypatch.setattr(single_instance, "QLocalSocket", _SockFactory())

    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "x.lock",
        server_name="server",
    )
    g = single_instance.SingleInstance(paths=paths)
    assert g.notify_primary(payload=b"X") is False


def test_close_best_effort_handles_missing_server_and_lock(tmp_path: Path) -> None:
    paths = single_instance.SingleInstancePaths(
        lock_path=tmp_path / "x.lock", server_name="s"
    )
    g = single_instance.SingleInstance(paths=paths)
    g.close()

