from __future__ import annotations

import importlib
import importlib.metadata
import logging
import os
import shutil
import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from voice_reader.application.services.narration_service import NarrationService
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.tts_engine_factory import TTSEngineFactory
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.infrastructure.audio.audio_streamer import SoundDeviceAudioStreamer
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.infrastructure.books.repository import LocalBookRepository
from voice_reader.infrastructure.cache.filesystem_cache import FilesystemCacheRepository
from voice_reader.infrastructure.bookmarks.json_bookmark_repository import (
    JSONBookmarkRepository,
)
from voice_reader.infrastructure.preferences.json_preferences_repository import (
    JSONPreferencesRepository,
)
from voice_reader.infrastructure.tts.voice_profile_repository import (
    KokoroVoiceProfileRepository,
)
from voice_reader.shared.config import Config
from voice_reader.shared.external_runtime import configure_packaged_runtime
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController
from voice_reader.version import APP_APPUSERMODELID, APP_NAME


def _env_truthy(name: str) -> bool:
    try:
        v = os.getenv(name, "")
    except Exception:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _preflight_imports(*, heavy: bool) -> tuple[int, str]:
    """Return (rc, report).

    rc is 0 when all imports succeed, otherwise 2.
    """

    # Keep this list small and stable. The goal is to validate the packaged
    # runtime has the critical wheels available, not to fully initialize them.
    modules = [
        # Basic stdlib/bootstrap sanity.
        "site",
        # Historically flaky in some packaging environments.
        "regex",
    ]
    if heavy:
        modules.extend(["spacy", "thinc", "torch", "transformers", "kokoro"])

    failures: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"IMPORT {name}: {exc!r}")
            # Optional extra context: dist metadata version lookup.
            try:
                ver = importlib.metadata.version(name)
                failures.append(f"DIST {name}: {ver}")
            except Exception as exc2:  # noqa: BLE001
                failures.append(f"DIST {name}: {exc2!r}")

    if failures:
        return 2, "\n".join(failures)

    return 0, "OK"


def exe_dir() -> Path:
    """Return directory containing the executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def set_windows_app_identity() -> None:
    """Ensure Windows groups the app correctly in the taskbar."""
    if os.name != "nt":
        return
    try:
        # Import inside the function so tests can monkeypatch `ctypes` via
        # `sys.modules` without having to reach into this module's globals.
        import ctypes  # noqa: WPS433 (intentional dynamic import for testability)

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_APPUSERMODELID
        )
    except Exception:
        pass


def find_runtime_icon() -> Path | None:
    """
    Locate runtime PNG icon beside the executable.

    Qt sometimes fails to decode ICO files in frozen apps, so we use PNG.
    """
    icon_path = exe_dir() / "narratex_256.png"
    if icon_path.exists():
        return icon_path
    return None


def program_base_dir() -> Path:
    try:
        return Path(sys.argv[0]).resolve().parent
    except Exception:
        return Path.cwd()


def append_startup_log(filename: str, text: str) -> None:
    try:
        path = program_base_dir() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(text.rstrip("\n") + "\n")
    except Exception:
        pass


def ensure_stdio() -> None:
    """Ensure stdout/stderr exist for GUI builds."""
    base = program_base_dir()

    if sys.stdout is None:
        try:
            sys.stdout = open(
                base / "NarrateX.runtime.out.txt",
                "a",
                buffering=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass

    if sys.stderr is None:
        try:
            sys.stderr = open(
                base / "NarrateX.runtime.err.txt",
                "a",
                buffering=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass


def main() -> int:
    try:
        ensure_stdio()

        # Must be set before any Qt object exists
        set_windows_app_identity()

        print("NarrateX: starting")
        append_startup_log(
            "NarrateX.startup.log.txt",
            f"start pid={os.getpid()} exe={sys.executable}",
        )

        configure_logging(logging.INFO)
        log = logging.getLogger("app")

        configure_packaged_runtime()

        # Preflight mode: do NOT start Qt. Used by installer + CI to validate the
        # runtime environment quickly.
        if _env_truthy("NARRATEX_PREFLIGHT"):
            heavy = _env_truthy("NARRATEX_PREFLIGHT_HEAVY")
            rc, report = _preflight_imports(heavy=heavy)
            if rc != 0:
                append_startup_log("NarrateX.startup.err.txt", report)
            return rc

        project_root = Path(__file__).resolve().parent
        config = Config.from_project_root(project_root)
        config.ensure_directories()

        preserve_cache = _env_truthy("NARRATEX_PRESERVE_CACHE")

        if not preserve_cache:
            try:
                shutil.rmtree(config.paths.cache_dir, ignore_errors=True)
                config.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                log.exception("Failed clearing cache")

        device = "cpu"

        converter = CalibreConverter(temp_books_dir=config.paths.temp_books_dir)
        parser = BookParser()
        book_repo = LocalBookRepository(converter=converter, parser=parser)

        cache_repo = FilesystemCacheRepository(cache_dir=config.paths.cache_dir)

        bookmark_repo = JSONBookmarkRepository(bookmarks_dir=config.paths.bookmarks_dir)
        bookmark_service = BookmarkService(repo=bookmark_repo)

        # Preferences persistence (small JSON file). Keep backwards-compatible
        # with older test stubs that don't provide `preferences_path`.
        try:
            preferences_path = config.paths.preferences_path
        except Exception:
            # Default beside bookmarks_dir (same data_root).
            preferences_path = config.paths.bookmarks_dir.parent / "preferences.json"

        preferences_repo = JSONPreferencesRepository(path=preferences_path)
        voice_repo = KokoroVoiceProfileRepository()
        voice_service = VoiceProfileService(repo=voice_repo)

        tts_engine = TTSEngineFactory().create()
        audio_streamer = SoundDeviceAudioStreamer(target_buffer_seconds=15.0)

        chunker = ChunkingService(min_chars=120, max_chars=220)

        narration_service = NarrationService(
            book_repo=book_repo,
            cache_repo=cache_repo,
            tts_engine=tts_engine,
            audio_streamer=audio_streamer,
            chunking_service=chunker,
            device=device,
            language=config.default_language,
            bookmark_service=bookmark_service,
            preferences_repo=preferences_repo,
        )

        # ----- Qt startup -----

        app = QApplication(sys.argv)

        # Best-effort: some tests replace QApplication with a minimal fake.
        if hasattr(app, "setApplicationName"):
            app.setApplicationName(APP_NAME)
        if hasattr(app, "setApplicationDisplayName"):
            app.setApplicationDisplayName(APP_NAME)

        if hasattr(app, "setDesktopFileName"):
            app.setDesktopFileName(APP_APPUSERMODELID)

        icon_path = find_runtime_icon()
        icon = QIcon(str(icon_path)) if icon_path else QIcon()

        if not icon.isNull() and hasattr(app, "setWindowIcon"):
            app.setWindowIcon(icon)

        window = MainWindow()

        if not icon.isNull() and hasattr(window, "setWindowIcon"):
            window.setWindowIcon(icon)

        UiController(
            window=window,
            narration_service=narration_service,
            bookmark_service=bookmark_service,
            voice_service=voice_service,
            device=device,
            engine_name=tts_engine.engine_name,
        )

        def on_quit() -> None:
            try:
                try:
                    narration_service.on_app_exit()
                except Exception:
                    log.exception("Failed saving resume position on app exit")
                narration_service.stop()
            except Exception:
                log.exception("Failed stopping narration")

        try:
            app.aboutToQuit.connect(on_quit)
        except Exception:
            log.exception("Failed connecting aboutToQuit")

        window.show()

        append_startup_log("NarrateX.startup.log.txt", "window shown")

        return app.exec()
    except SystemExit:
        raise
    except Exception:
        # Startup failures should be visible even in windowed builds.
        append_startup_log("NarrateX.startup.err.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
