from __future__ import annotations

import ctypes
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
from voice_reader.application.services.tts_engine_factory import TTSEngineFactory
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.infrastructure.audio.audio_streamer import SoundDeviceAudioStreamer
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.infrastructure.books.repository import LocalBookRepository
from voice_reader.infrastructure.cache.filesystem_cache import FilesystemCacheRepository
from voice_reader.infrastructure.tts.voice_profile_repository import (
    KokoroVoiceProfileRepository,
)
from voice_reader.shared.config import Config
from voice_reader.shared.external_runtime import configure_packaged_runtime
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController
from voice_reader.version import APP_APPUSERMODELID, APP_NAME


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

    project_root = Path(__file__).resolve().parent
    config = Config.from_project_root(project_root)
    config.ensure_directories()

    preserve_cache = os.getenv("NARRATEX_PRESERVE_CACHE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

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
    )

    # ----- Qt startup -----

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName(APP_APPUSERMODELID)

    icon_path = find_runtime_icon()
    icon = QIcon(str(icon_path)) if icon_path else QIcon()

    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()

    if not icon.isNull():
        window.setWindowIcon(icon)

    UiController(
        window=window,
        narration_service=narration_service,
        voice_service=voice_service,
        device=device,
        engine_name=tts_engine.engine_name,
    )

    def on_quit() -> None:
        try:
            narration_service.stop()
        except Exception:
            log.exception("Failed stopping narration")

    try:
        app.aboutToQuit.connect(on_quit)
    except Exception:
        pass

    window.show()

    append_startup_log("NarrateX.startup.log.txt", "window shown")

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())