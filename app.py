from __future__ import annotations

import os
import sys

from voice_reader.shared.startup_diagnostics import (
    enforce_supported_python,
    running_frozen,
    running_in_flatpak,
)

# Before the heavy imports: on an unsupported interpreter nothing installed, so
# the next import fails with a message that never mentions the real cause. Both
# the Flatpak and the PyInstaller bundle (e.g. the macOS .app on Python 3.13)
# ship their own known-good wheels, so the source-venv check is skipped there.
enforce_supported_python(
    sys.version_info,
    write=lambda m: print(m, file=sys.stderr),
    in_managed_runtime=(
        running_in_flatpak(path_exists=os.path.exists)
        or running_frozen(frozen=getattr(sys, "frozen", False))
    ),
)

import importlib
import importlib.metadata
import logging
import multiprocessing as mp
import shutil
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication

from voice_reader.ui._app_icon import build_runtime_icon, set_windows_app_identity
from voice_reader.shared.config import Config
from voice_reader.shared.external_runtime import configure_packaged_runtime
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.shared.startup_diagnostics import (
    preflight_imports as _preflight_imports,
)
from voice_reader.shared.startup_io import append_startup_log, ensure_stdio
from voice_reader.shared.startup_lifecycle import shutdown, start_tts_warmup
from voice_reader.shared.startup_ui import (
    center_window_on_screen,
    default_lock_dir,
    maybe_show_splash,
)
from voice_reader.bootstrap import install_wiring_placeholders, resolve_app_wiring
from voice_reader.version import APP_APPUSERMODELID, APP_NAME

# Several unit tests monkeypatch the wiring names on this module to avoid the
# heavy imports, which only works if the names already exist.
install_wiring_placeholders(globals())


def _run_model_preflight(app) -> bool:  # noqa: ANN001
    from voice_reader.ui.model_download_dialog import maybe_download_model

    return maybe_download_model(app)


def _env_truthy(name: str) -> bool:
    try:
        v = os.getenv(name, "")
    except Exception:  # noqa: BLE001
        # Degrades to "flag not set". Tests replace os.getenv with stubs that
        # can raise; an unreadable environment must not stop startup for a
        # flag that is off by default anyway.
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    try:
        # freeze_support() handles Windows frozen re-entry. On macOS (spawn),
        # this module is re-executed as __main__ in the child; the parent-process
        # guard exits before Qt or any heavy init runs.
        mp.freeze_support()
        if mp.parent_process() is not None:
            return 0

        ensure_stdio()

        # Must be set before any Qt object exists
        set_windows_app_identity()

        append_startup_log(
            "NarrateX.startup.log.txt",
            f"start pid={os.getpid()} exe={sys.executable}",
        )

        configure_logging(logging.INFO)
        log = logging.getLogger("app")
        # This is a windowed application, so a line on stdout goes somewhere no
        # user will ever look. The startup log above is the durable record and
        # the logger is where a running-session message belongs.
        log.info("%s starting", APP_NAME)

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

        # Suppress a spurious D-Bus portal registration warning emitted on some
        # desktops when the session bus already associates an app ID before Qt
        # tries to register one (benign, no functional impact).
        os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.services=false")

        app = QApplication(sys.argv)

        # Best-effort: some tests replace QApplication with a minimal fake.
        if hasattr(app, "setApplicationName"):
            app.setApplicationName(APP_NAME)
        if hasattr(app, "setApplicationDisplayName"):
            app.setApplicationDisplayName(APP_NAME)

        if hasattr(app, "setDesktopFileName"):
            app.setDesktopFileName(APP_APPUSERMODELID)

        icon = build_runtime_icon()

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
                try:
                    app.processEvents()
                except Exception:  # noqa: BLE001
                    # Degrades to the window raising on the next event-loop
                    # turn instead of immediately. Nudging Qt is a courtesy;
                    # failing to nudge it must not break activation.
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
        except Exception:  # noqa: BLE001
            # Degrades to running without the guard. The single-instance lock
            # is a convenience (a second launch raises the first window); a
            # lock directory that cannot be created must not stop the
            # application opening at all, so this run continues as primary.
            log.exception("Single-instance guard unavailable; running unguarded")
            instance_guard = None
            is_primary = True

        if not is_primary and instance_guard is not None:
            try:
                instance_guard.notify_primary()
            except Exception:  # noqa: BLE001
                # Degrades to the first window not being raised. This process
                # is the second instance either way and must still exit 0
                # rather than report a failure the user cannot act on.
                log.exception("Could not notify the running instance")
            return 0

        # ----- Splash (show before heavy imports) -----

        project_root = Path(__file__).resolve().parent
        splash = maybe_show_splash(
            app=app,
            icon=icon,
            project_root=project_root,
            enabled=(not _env_truthy("NARRATEX_DISABLE_SPLASH")),
        )

        # ----- Model pre-flight: download Kokoro weights if not cached -----
        # Runs once on first launch; shows a progress dialog while downloading.
        if not _run_model_preflight(app):
            return 1  # user was shown an error dialog; exit cleanly

        # ----- Heavy app wiring (after splash is visible) -----

        resolve_app_wiring(globals(), tick_fn=app.processEvents)

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
            except Exception:  # noqa: BLE001
                # Deliberately broad; deliberately not narrowed to OSError.
                # Degrades to starting with whatever cache is already there,
                # which the repositories treat as a miss and re-synthesise. A
                # stale cache is a slow first chunk; an exception escaping here
                # is an application that never appears at all.
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
        except AttributeError:
            # Narrowed: the only way this attribute is absent is an older test
            # stub for the paths object. Degrades to the same location the real
            # config uses, beside bookmarks_dir under the same data root.
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
            book_loader=_g("load_book_in_subprocess"),
        )

        try:
            app.aboutToQuit.connect(
                lambda: shutdown(controller, narration_service, log=log)
            )
        except Exception:  # noqa: BLE001
            # Degrades to no orderly shutdown on quit: the resume position is
            # not saved and the audio device is released by process exit
            # instead. Worth logging loudly and not worth refusing to start
            # over, since the fake QApplication some tests use has no signals.
            log.exception("Failed connecting aboutToQuit")

        window.show()

        center_window_on_screen(app, window)

        # Ensure the first paint happens before we hide the splash.
        try:
            app.processEvents()
        except Exception:  # noqa: BLE001
            # Degrades to the splash being replaced a frame later. The fake
            # QApplication some tests use has no processEvents at all.
            pass

        if splash is not None:
            try:
                fin = getattr(splash, "finish", None)
                if callable(fin):
                    fin(window)
            except Exception:  # noqa: BLE001
                # Degrades to the splash closing on its own timer rather than
                # handing off to the window. Never worth failing a launch that
                # has already produced a usable window.
                log.exception("Splash handover failed")

        if pending_activate:
            from voice_reader.shared.startup_ui import activate_window

            activate_window(window)

        append_startup_log("NarrateX.startup.log.txt", "window shown")

        start_tts_warmup(voice_service, narration_service, log=log)

        return app.exec()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        # Not a swallow: this records and re-raises. A windowed build has no
        # console, so an unhandled startup failure would otherwise leave the
        # user with a process that exits silently and no trace of why.
        append_startup_log("NarrateX.startup.err.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    # Required for PyInstaller/Windows when using multiprocessing spawn.
    mp.freeze_support()
    raise SystemExit(main())
