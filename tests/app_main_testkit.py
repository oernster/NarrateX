from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import app


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []

    def connect(self, cb):  # noqa: ANN001 (test double)
        self._callbacks.append(cb)

    def emit(self) -> None:
        for cb in list(self._callbacks):
            cb()


class FakeQApplication:
    def __init__(self, argv, *, about_to_quit=None) -> None:  # noqa: ANN001
        del argv
        self.aboutToQuit = about_to_quit or FakeSignal()
        self._exec_called = False

    def setApplicationName(self, _):  # noqa: ANN001
        return

    def setApplicationDisplayName(self, _):  # noqa: ANN001
        return

    def setDesktopFileName(self, _):  # noqa: ANN001
        return

    def setWindowIcon(self, _):  # noqa: ANN001
        return

    def exec(self) -> int:
        self._exec_called = True
        # Simulate the app quitting immediately.
        try:
            self.aboutToQuit.emit()
        except Exception:
            # Some tests provide a minimal aboutToQuit object.
            pass
        return 0


class FakeWindow:
    def __init__(self) -> None:
        self.shown = False

    def setWindowIcon(self, _):  # noqa: ANN001
        return

    def show(self) -> None:
        self.shown = True


class FakeUiController:
    def __init__(self, **kwargs) -> None:
        # Ensure wiring passes the essential dependencies.
        self.kwargs = kwargs


class FakeLogger:
    def __init__(self) -> None:
        self.exception_calls = 0

    def warning(self, *a, **k):  # noqa: ANN001
        return

    def debug(self, *a, **k):  # noqa: ANN001
        return

    def exception(self, *a, **k):  # noqa: ANN001
        self.exception_calls += 1


@dataclass(frozen=True, slots=True)
class MainWiringRig:
    rmtree_calls: list[Path]
    stop_calls: dict[str, int]
    qapp: FakeQApplication
    logger: FakeLogger | None


def patch_app_main_wiring(
    monkeypatch,
    tmp_path: Path,
    *,
    preserve_cache: bool,
    qapp_instance: FakeQApplication | None = None,
    logger: FakeLogger | None = None,
    rmtree_raises: bool = False,
    stop_raises: bool = False,
) -> MainWiringRig:
    """Patch `app.main()` dependencies with lightweight fakes.

    The goal is to keep tests stable while avoiding heavy UI/infra imports.
    """

    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))

    if preserve_cache:
        monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")
    else:
        monkeypatch.delenv("NARRATEX_PRESERVE_CACHE", raising=False)

    if logger is not None:
        # Patch `app.logging` without mutating the global `logging` module.
        monkeypatch.setattr(
            app,
            "logging",
            SimpleNamespace(INFO=20, getLogger=lambda name=None: logger),
        )
        monkeypatch.setattr(app, "configure_logging", lambda level=None: None)

    rmtree_calls: list[Path] = []

    def _rmtree(p, ignore_errors: bool):  # noqa: ANN001
        del ignore_errors
        if rmtree_raises:
            raise RuntimeError("boom")
        rmtree_calls.append(Path(p))

    # Patch `app.shutil` without mutating the global `shutil` module used by pytest.
    monkeypatch.setattr(app, "shutil", SimpleNamespace(rmtree=_rmtree))

    fake_qapp = qapp_instance or FakeQApplication([])
    monkeypatch.setattr(app, "QApplication", lambda argv: fake_qapp)
    monkeypatch.setattr(app, "MainWindow", FakeWindow)
    monkeypatch.setattr(app, "UiController", FakeUiController)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
                bookmarks_dir=tmp_path / "bookmarks",
            )
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)
            self.paths.bookmarks_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        app.Config, "from_project_root", lambda project_root: _FakeConfig()
    )

    # Patch infra construction to avoid importing heavy deps.
    monkeypatch.setattr(
        app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(
        app,
        "LocalBookRepository",
        lambda **kwargs: SimpleNamespace(
            load=lambda p: SimpleNamespace(title="t", normalized_text="x")
        ),
    )
    monkeypatch.setattr(
        app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(
        app, "KokoroVoiceProfileRepository", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(
        app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace()
    )
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    monkeypatch.setattr(
        app,
        "TTSEngineFactory",
        lambda: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="fake")),
    )

    stop_calls = {"n": 0}

    def _stop() -> None:
        stop_calls["n"] += 1
        if stop_raises:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=_stop)
    )

    return MainWiringRig(
        rmtree_calls=rmtree_calls,
        stop_calls=stop_calls,
        qapp=fake_qapp,
        logger=logger,
    )
