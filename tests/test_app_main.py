from __future__ import annotations

from pathlib import Path

import app

from tests.app_main_testkit import (
    FakeLogger,
    FakeQApplication,
    patch_app_main_wiring,
)


def test_main_preserve_cache_skips_rmtree(monkeypatch, tmp_path: Path) -> None:
    rig = patch_app_main_wiring(monkeypatch, tmp_path, preserve_cache=True)

    # Act
    rc = app.main()

    # Assert
    assert rc == 0
    assert rig.rmtree_calls == []
    assert rig.stop_calls["n"] == 1


def test_main_clears_cache_and_registers_quit_handler(
    monkeypatch, tmp_path: Path
) -> None:
    # Make cache dir exist so clearing has a real target.
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    rig = patch_app_main_wiring(monkeypatch, tmp_path, preserve_cache=False)

    rc = app.main()

    assert rc == 0
    assert rig.rmtree_calls, "Expected cache clearing via shutil.rmtree"
    assert (
        rig.stop_calls["n"] == 1
    ), "Expected quit hook to call narration_service.stop()"


def test_main_cache_clear_failure_is_logged_and_continues(
    monkeypatch, tmp_path: Path
) -> None:
    fake_logger = FakeLogger()
    rig = patch_app_main_wiring(
        monkeypatch,
        tmp_path,
        preserve_cache=False,
        logger=fake_logger,
        rmtree_raises=True,
    )

    rc = app.main()
    assert rc == 0
    assert rig.logger is not None
    assert rig.logger.exception_calls >= 1


def test_main_about_to_quit_connect_failure_is_logged(
    monkeypatch, tmp_path: Path
) -> None:
    class _BadQuitSig:
        def emit(self) -> None:
            # If exec() triggers a quit, the signal should still be callable.
            return

        def connect(self, cb):
            del cb
            raise RuntimeError("no")

    fake_logger = FakeLogger()
    fake_qapp = FakeQApplication([], about_to_quit=_BadQuitSig())
    rig = patch_app_main_wiring(
        monkeypatch,
        tmp_path,
        preserve_cache=True,
        qapp_instance=fake_qapp,
        logger=fake_logger,
    )

    assert app.main() == 0
    assert rig.logger is not None
    assert rig.logger.exception_calls >= 1


def test_main_on_quit_stop_failure_is_logged(monkeypatch, tmp_path: Path) -> None:
    fake_logger = FakeLogger()
    rig = patch_app_main_wiring(
        monkeypatch,
        tmp_path,
        preserve_cache=True,
        logger=fake_logger,
        stop_raises=True,
    )

    assert app.main() == 0
    assert rig.logger is not None
    assert rig.logger.exception_calls >= 1
