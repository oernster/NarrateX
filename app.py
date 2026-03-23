from __future__ import annotations

import importlib
import importlib.metadata
import logging
import multiprocessing as mp
import os
import shutil
import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from voice_reader.shared.config import Config
from voice_reader.shared.external_runtime import configure_packaged_runtime
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.shared.startup_diagnostics import (
    append_startup_log as _append_startup_log,
    ensure_stdio as _ensure_stdio,
    preflight_imports as _preflight_imports,
    program_base_dir as _program_base_dir,
)
from voice_reader.shared.startup_ui import default_lock_dir, maybe_show_splash
from voice_reader.bootstrap import resolve_app_wiring
from voice_reader.version import APP_APPUSERMODELID, APP_NAME

# --- Test hooks / lazy import placeholders ---
#
# Several unit tests monkeypatch these names on the `app` module to avoid heavy
# imports. Keep them defined at module import time so monkeypatching remains
# stable even though the real imports happen lazily inside `main()`.
for _sym in [
    "MainWindow",
    "UiController",
    "NarrationService",
    "BookmarkService",
    "IdeaMapService",
    "IdeaIndexingManager",
    "StructuralBookmarkService",
    "TTSEngineFactory",
    "CoverExtractor",
    "VoiceProfileService",
    "ChunkingService",
    "SoundDeviceAudioStreamer",
    "CalibreConverter",
    "BookParser",
    "LocalBookRepository",
    "FilesystemCacheRepository",
    "JSONBookmarkRepository",
    "JSONIdeaIndexRepository",
    "JSONPreferencesRepository",
    "KokoroVoiceProfileRepository",
]:
    globals().setdefault(_sym, None)


def _env_truthy(name: str) -> bool:
    try:
        v = os.getenv(name, "")
    except Exception:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


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
    return _program_base_dir(argv0=(sys.argv[0] if sys.argv else ""), cwd=Path.cwd)


def append_startup_log(filename: str, text: str) -> None:
    return _append_startup_log(
        base_dir=program_base_dir(),
        filename=filename,
        text=text,
        open_fn=open,
    )


def ensure_stdio() -> None:
    base = program_base_dir()
    out, err = _ensure_stdio(
        base_dir=base,
        stdout=sys.stdout,
        stderr=sys.stderr,
        open_fn=open,
    )
    sys.stdout = out
    sys.stderr = err


def main() -> int:
    try:
        # IMPORTANT (Windows frozen builds + multiprocessing):
        # Our Ideas indexing runs in a spawned child process. In a frozen
        # application (PyInstaller), Windows uses the "spawn" start method which
        # re-launches the executable. Without mp.freeze_support(), the child can
        # incorrectly execute the normal app startup path and create a second
        # (blank) Qt window.
        mp.freeze_support()

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
            rc, report = _preflight_imports(
                heavy=heavy,
                import_module=importlib.import_module,
                dist_version=importlib.metadata.version,
            )
            if rc != 0:
                append_startup_log("NarrateX.startup.err.txt", report)
            return rc

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

        # ----- Single instance guard -----

        allow_multi = _env_truthy("NARRATEX_ALLOW_MULTIINSTANCE")

        # Activation messages can arrive at any time (e.g. user clicks the taskbar
        # icon while the app is already running). If the window already exists,
        # raise/focus it immediately; otherwise defer until after creation.
        window = None
        pending_activate: bool = False

        def _on_activate() -> None:
            nonlocal pending_activate
            if window is None:
                pending_activate = True
                return
            # Local import keeps `app` tests simple (they monkeypatch this module
            # heavily and expect only a subset of names to exist).
            from voice_reader.shared.startup_ui import activate_window

            try:
                activate_window(window)
            finally:
                # Best-effort: help the WM/Qt process the activation.
                try:
                    app.processEvents()
                except Exception:
                    pass

        instance_guard = None
        is_primary = True
        try:
            lock_dir = default_lock_dir(app_name=APP_NAME)
            from voice_reader.shared.startup_ui import setup_single_instance

            instance_guard, is_primary = setup_single_instance(
                app=app,
                app_id=APP_APPUSERMODELID,
                allow_multi=allow_multi,
                lock_dir=lock_dir,
                on_activate=_on_activate,
            )
        except Exception:
            instance_guard = None
            is_primary = True

        if not is_primary and instance_guard is not None:
            try:
                instance_guard.notify_primary()
            except Exception:
                pass
            return 0

        # ----- Splash (show before heavy imports) -----

        project_root = Path(__file__).resolve().parent
        splash = maybe_show_splash(
            app=app,
            icon=icon,
            project_root=project_root,
            enabled=(not _env_truthy("NARRATEX_DISABLE_SPLASH")),
        )

        # ----- Heavy app wiring (after splash is visible) -----

        resolve_app_wiring(globals())

        def _g(name: str):  # noqa: ANN001
            return globals()[name]

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

        converter = _g("CalibreConverter")(temp_books_dir=config.paths.temp_books_dir)
        parser = _g("BookParser")()
        book_repo = _g("LocalBookRepository")(converter=converter, parser=parser)

        cache_repo = _g("FilesystemCacheRepository")(cache_dir=config.paths.cache_dir)

        bookmark_repo = _g("JSONBookmarkRepository")(
            bookmarks_dir=config.paths.bookmarks_dir
        )
        bookmark_service = _g("BookmarkService")(repo=bookmark_repo)

        idea_repo = _g("JSONIdeaIndexRepository")(
            bookmarks_dir=config.paths.bookmarks_dir
        )
        idea_map_service = _g("IdeaMapService")(repo=idea_repo)
        idea_indexing_manager = _g("IdeaIndexingManager")(repo=idea_repo)

        structural_bookmark_service = _g("StructuralBookmarkService")()

        # Preferences persistence (small JSON file). Keep backwards-compatible
        # with older test stubs that don't provide `preferences_path`.
        try:
            preferences_path = config.paths.preferences_path
        except Exception:
            # Default beside bookmarks_dir (same data_root).
            preferences_path = config.paths.bookmarks_dir.parent / "preferences.json"

        preferences_repo = _g("JSONPreferencesRepository")(path=preferences_path)
        voice_repo = _g("KokoroVoiceProfileRepository")()
        voice_service = _g("VoiceProfileService")(repo=voice_repo)

        tts_engine = _g("TTSEngineFactory")().create()
        audio_streamer = _g("SoundDeviceAudioStreamer")(target_buffer_seconds=15.0)

        chunker = _g("ChunkingService")(min_chars=120, max_chars=220)

        narration_service = _g("NarrationService")(
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

        window = _g("MainWindow")()

        if not icon.isNull() and hasattr(window, "setWindowIcon"):
            window.setWindowIcon(icon)

        controller = _g("UiController")(
            window=window,
            narration_service=narration_service,
            bookmark_service=bookmark_service,
            idea_map_service=idea_map_service,
            idea_indexing_manager=idea_indexing_manager,
            structural_bookmark_service=structural_bookmark_service,
            voice_service=voice_service,
            device=device,
            engine_name=tts_engine.engine_name,
            cover_extractor=_g("CoverExtractor")(),
        )

        def on_quit() -> None:
            try:
                try:
                    controller.on_app_exit()
                except Exception:
                    log.exception("Failed stopping Ideas indexing on app exit")
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

        # Ensure the first paint happens before we hide the splash.
        try:
            app.processEvents()
        except Exception:
            pass

        if splash is not None:
            try:
                fin = getattr(splash, "finish", None)
                if callable(fin):
                    fin(window)
            except Exception:
                pass

        if pending_activate:
            from voice_reader.shared.startup_ui import activate_window

            activate_window(window)

        append_startup_log("NarrateX.startup.log.txt", "window shown")

        return app.exec()
    except SystemExit:
        raise
    except Exception:
        # Startup failures should be visible even in windowed builds.
        append_startup_log("NarrateX.startup.err.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    # Required for PyInstaller/Windows when using multiprocessing spawn.
    mp.freeze_support()
    raise SystemExit(main())
