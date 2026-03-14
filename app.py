"""Application entrypoint.

This module is the first Python code executed in the packaged EXE.

Important packaging note:
When building a Windows GUI executable (e.g. PyInstaller), startup failures can be silent (no console).
We therefore keep imports light at module import time and write a best-effort
startup crash log near the executable.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

import importlib
import importlib.metadata
import traceback

from voice_reader.shared.config import Config
from voice_reader.shared.external_runtime import configure_packaged_runtime
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.shared.resources import find_app_icon_path
from voice_reader.shared.windows_integration import set_app_user_model_id
from voice_reader.version import APP_APPUSERMODELID, APP_NAME

# NOTE:
# We intentionally avoid importing PySide6 at module import time.
# Some packaged failures (Qt platform plugins, DLL search path) can occur before
# we have configured `dist/ext` and before stdout/stderr redirection is active.
#
# Tests monkeypatch these names, so they must exist on the module.
QApplication = None
QIcon = None
MainWindow = None
UiController = None

# Remaining wiring imports are deferred to `main()` so we can write a crash log
# even if they fail.
NarrationService = None
TTSEngineFactory = None
VoiceProfileService = None
ChunkingService = None
SoundDeviceAudioStreamer = None
CalibreConverter = None
BookParser = None
LocalBookRepository = None
FilesystemCacheRepository = None
KokoroVoiceProfileRepository = None


def main() -> int:
    # Best-effort startup log: in GUI mode, fatal errors may otherwise vanish.
    # This is separate from the normal logging configuration.
    def _program_base_dir() -> Path:
        try:
            return Path(sys.argv[0]).resolve().parent
        except Exception:
            return Path.cwd()

    def _append_startup_log(filename: str, text: str) -> None:
        try:
            path = _program_base_dir() / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8", errors="replace") as f:
                f.write(text.rstrip("\n") + "\n")
        except Exception:
            # Never crash while trying to log a crash.
            pass

    def _ensure_stdio() -> None:
        """Ensure `sys.stdout`/`sys.stderr` are usable file objects.

        Some Windows GUI builds can have `sys.stderr is None` (pythonw-like
        behavior). Some dependencies (notably `loguru`, used by Kokoro) attempt
        to log to `sys.stderr` during import, which will crash if it is `None`.
        """

        base = _program_base_dir()
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

    try:
        _ensure_stdio()

        # Force creation of early stdout/stderr capture files (when enabled)
        # by emitting at least one line early.
        print("NarrateX: starting")
        _append_startup_log(
            "NarrateX.startup.log.txt",
            f"start pid={os.getpid()} exe={sys.executable} argv0={sys.argv[0] if sys.argv else ''}",
        )

        configure_logging(logging.INFO)
        log = logging.getLogger("app")

        # If the distribution ships heavy dependencies beside the exe (dist/ext),
        # add them to sys.path before importing/initializing services.
        configure_packaged_runtime()

        # Optional preflight mode to validate external runtime deps without
        # needing a full GUI run.
        if os.getenv("NARRATEX_PREFLIGHT", "").strip().lower() in {"1", "true", "yes"}:
            failures: list[str] = []

            def _check_import(mod: str) -> None:
                try:
                    importlib.import_module(mod)
                except Exception as e:
                    failures.append(
                        "\n".join(
                            [
                                f"IMPORT {mod}: {type(e).__name__}: {e}",
                                traceback.format_exc().rstrip(),
                            ]
                        )
                    )

            def _check_dist(dist: str) -> None:
                try:
                    v = importlib.metadata.version(dist)
                    _append_startup_log("NarrateX.startup.log.txt", f"dist {dist}={v}")
                except Exception as e:
                    failures.append(
                        "\n".join(
                            [
                                f"DIST {dist}: {type(e).__name__}: {e}",
                                traceback.format_exc().rstrip(),
                            ]
                        )
                    )

            # Light in-process imports only (pure-Python / low-risk).
            for m in ["site", "regex"]:
                _check_import(m)

            preflight_heavy = os.getenv("NARRATEX_PREFLIGHT_HEAVY", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }

            if preflight_heavy:
                # Heavy imports: can still crash the process if a native module
                # segfaults. Keep behind an explicit opt-in.
                for m in [
                    "spacy",
                    "thinc",
                    "torch",
                    "transformers",
                    "kokoro",
                ]:
                    _check_import(m)

            # Distributions used by runtime version checks.
            for d in [
                "tqdm",
                "regex",
                "requests",
                "packaging",
                "filelock",
                "PyYAML",
                "spacy",
                "thinc",
                "transformers",
                "torch",
                "numpy",
            ]:
                _check_dist(d)

            if failures:
                _append_startup_log(
                    "NarrateX.startup.err.txt",
                    "NARRATEX_PREFLIGHT failed:\n" + "\n".join(failures),
                )
                return 2
            _append_startup_log("NarrateX.startup.log.txt", "NARRATEX_PREFLIGHT ok")
            return 0

        # Windows taskbar identity must be set before creating any windows.
        set_app_user_model_id(APP_APPUSERMODELID)

        project_root = Path(__file__).resolve().parent
        config = Config.from_project_root(project_root)
        config.ensure_directories()

    # Cache policy:
    # For now we ALWAYS clear synthesized audio cache on launch, so changes to
    # parsing/sanitization/voice/reference audio are reflected immediately.
    #
    # If you want to keep cache for faster startup, set:
    #   NARRATEX_PRESERVE_CACHE=1
        preserve_cache = os.getenv("NARRATEX_PRESERVE_CACHE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if not preserve_cache:
            try:
                shutil.rmtree(config.paths.cache_dir, ignore_errors=True)
                config.paths.cache_dir.mkdir(parents=True, exist_ok=True)
                log.warning(
                    "Cleared cache dir on launch (set NARRATEX_PRESERVE_CACHE=1 to disable): %s",
                    config.paths.cache_dir.as_posix(),
                )
            except Exception:
                log.exception("Failed to clear cache on launch")

        # Resolve deferred imports (allows tests to monkeypatch these symbols).
        global QApplication, QIcon, MainWindow, UiController
        global NarrationService, TTSEngineFactory, VoiceProfileService
        global ChunkingService, SoundDeviceAudioStreamer
        global CalibreConverter, BookParser, LocalBookRepository
        global FilesystemCacheRepository, KokoroVoiceProfileRepository

        if QApplication is None:
            from PySide6.QtWidgets import QApplication as _QApplication

            QApplication = _QApplication
        if QIcon is None:
            from PySide6.QtGui import QIcon as _QIcon

            QIcon = _QIcon
        if MainWindow is None:
            from voice_reader.ui.main_window import MainWindow as _MainWindow

            MainWindow = _MainWindow
        if UiController is None:
            from voice_reader.ui.ui_controller import UiController as _UiController

            UiController = _UiController

        if NarrationService is None:
            from voice_reader.application.services.narration_service import (
                NarrationService as _NarrationService,
            )

            NarrationService = _NarrationService
        if TTSEngineFactory is None:
            from voice_reader.application.services.tts_engine_factory import (
                TTSEngineFactory as _TTSEngineFactory,
            )

            TTSEngineFactory = _TTSEngineFactory
        if VoiceProfileService is None:
            from voice_reader.application.services.voice_profile_service import (
                VoiceProfileService as _VoiceProfileService,
            )

            VoiceProfileService = _VoiceProfileService
        if ChunkingService is None:
            from voice_reader.domain.services.chunking_service import (
                ChunkingService as _ChunkingService,
            )

            ChunkingService = _ChunkingService
        if SoundDeviceAudioStreamer is None:
            from voice_reader.infrastructure.audio.audio_streamer import (
                SoundDeviceAudioStreamer as _SoundDeviceAudioStreamer,
            )

            SoundDeviceAudioStreamer = _SoundDeviceAudioStreamer
        if CalibreConverter is None:
            from voice_reader.infrastructure.books.converter import (
                CalibreConverter as _CalibreConverter,
            )

            CalibreConverter = _CalibreConverter
        if BookParser is None:
            from voice_reader.infrastructure.books.parser import BookParser as _BookParser

            BookParser = _BookParser
        if LocalBookRepository is None:
            from voice_reader.infrastructure.books.repository import (
                LocalBookRepository as _LocalBookRepository,
            )

            LocalBookRepository = _LocalBookRepository
        if FilesystemCacheRepository is None:
            from voice_reader.infrastructure.cache.filesystem_cache import (
                FilesystemCacheRepository as _FilesystemCacheRepository,
            )

            FilesystemCacheRepository = _FilesystemCacheRepository
        if KokoroVoiceProfileRepository is None:
            from voice_reader.infrastructure.tts.voice_profile_repository import (
                KokoroVoiceProfileRepository as _KokoroVoiceProfileRepository,
            )

            KokoroVoiceProfileRepository = _KokoroVoiceProfileRepository

        # Kokoro is CPU-only; keep a constant `device` for interface compatibility.
        device = "cpu"

        # Infrastructure
        converter = CalibreConverter(temp_books_dir=config.paths.temp_books_dir)
        parser = BookParser()
        book_repo = LocalBookRepository(converter=converter, parser=parser)
        cache_repo = FilesystemCacheRepository(cache_dir=config.paths.cache_dir)
        voice_repo = KokoroVoiceProfileRepository()
        voice_service = VoiceProfileService(repo=voice_repo)

        tts_engine = TTSEngineFactory().create()
        audio_streamer = SoundDeviceAudioStreamer(target_buffer_seconds=15.0)

    # NOTE: XTTS warns/truncates when text > ~250 chars for language='en'.
    # Keep chunks comfortably under that to avoid truncated audio (which can
    # sound like stutters/restarts/jumps between sentence groups).
        chunker = ChunkingService(min_chars=120, max_chars=220)

        narration_service = NarrationService(
            book_repo=book_repo,
            cache_repo=cache_repo,
            tts_engine=tts_engine,
            audio_streamer=audio_streamer,
            chunking_service=chunker,
            device=device,
            language=config.default_language,
        )

        # UI
        app = QApplication([])

    # Set a stable application identity for the OS.
        try:
            app.setApplicationName(APP_NAME)
            app.setApplicationDisplayName(APP_NAME)
        except Exception:
            # Older bindings/platform quirks shouldn't stop startup.
            pass

        icon_path = find_app_icon_path(project_root=project_root)
        if icon_path is not None:
            try:
                app_icon = QIcon(str(icon_path))
                app.setWindowIcon(app_icon)
            except Exception:
                log.exception("Failed to set application icon")

        window = MainWindow()
        if icon_path is not None:
            try:
                window.setWindowIcon(QIcon(str(icon_path)))
            except Exception:
                log.exception("Failed to set main window icon")
        UiController(
            window=window,
            narration_service=narration_service,
            voice_service=voice_service,
            device=device,
            engine_name=tts_engine.engine_name,
        )

    # Ensure background threads are stopped cleanly on window close / app quit.
        def _on_quit() -> None:
            try:
                narration_service.stop()
            except Exception:
                log.exception("Failed to stop narration on quit")

        try:
            app.aboutToQuit.connect(_on_quit)
        except Exception:
            log.exception("Failed to register aboutToQuit handler")

        window.show()
        _append_startup_log("NarrateX.startup.log.txt", "window shown; entering event loop")
        return app.exec()
    except SystemExit:
        raise
    except Exception:
        _append_startup_log("NarrateX.startup.err.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
