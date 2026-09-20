"""Composition root helper.

This module exists to keep entrypoints small while still making wiring explicit.

Hard rule enforced by structural tests:
- Only entrypoints (e.g. [`main()`](app.py:176) and installer entrypoints) may
  import [`voice_reader.bootstrap`](voice_reader/bootstrap.py:1).
- Other modules must not depend on this module.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

_APP_WIRING_IMPORTS: Mapping[str, tuple[str, str]] = {
    # Application layer
    "NarrationService": (
        "voice_reader.application.services.narration_service",
        "NarrationService",
    ),
    "BookmarkService": (
        "voice_reader.application.services.bookmark_service",
        "BookmarkService",
    ),
    "IdeaMapService": (
        "voice_reader.application.services.idea_map_service",
        "IdeaMapService",
    ),
    "IdeaIndexingManager": (
        "voice_reader.application.services.idea_indexing_manager",
        "IdeaIndexingManager",
    ),
    "ShelfScanner": (
        "voice_reader.application.services.shelf.scanning",
        "ShelfScanner",
    ),
    "ShelfLibrary": (
        "voice_reader.application.services.shelf.library",
        "ShelfLibrary",
    ),
    "ShelfCovers": (
        "voice_reader.application.services.shelf.covers",
        "ShelfCovers",
    ),
    "StructuralBookmarkService": (
        "voice_reader.application.services.structural_bookmark_service",
        "StructuralBookmarkService",
    ),
    "VoiceProfileService": (
        "voice_reader.application.services.voice_profile_service",
        "VoiceProfileService",
    ),
    "UpdateService": (
        "voice_reader.application.services.update_service",
        "UpdateService",
    ),
    "platform_key_for": (
        "voice_reader.application.services.update_service",
        "platform_key_for",
    ),
    # Domain layer
    "ChunkingService": (
        "voice_reader.domain.services.chunking_service",
        "ChunkingService",
    ),
    # Infrastructure layer
    "TTSEngineFactory": (
        "voice_reader.infrastructure.tts.tts_engine_factory",
        "TTSEngineFactory",
    ),
    "CoverExtractor": (
        "voice_reader.infrastructure.books.cover_extractor",
        "CoverExtractor",
    ),
    "GitHubReleaseSource": (
        "voice_reader.infrastructure.update.github_release_source",
        "GitHubReleaseSource",
    ),
    "SoundDeviceAudioStreamer": (
        "voice_reader.infrastructure.audio.audio_streamer",
        "SoundDeviceAudioStreamer",
    ),
    "CalibreConverter": (
        "voice_reader.infrastructure.books.converter",
        "CalibreConverter",
    ),
    "BookParser": ("voice_reader.infrastructure.books.parser", "BookParser"),
    "LocalBookRepository": (
        "voice_reader.infrastructure.books.repository",
        "LocalBookRepository",
    ),
    "FilesystemCacheRepository": (
        "voice_reader.infrastructure.cache.filesystem_cache",
        "FilesystemCacheRepository",
    ),
    "JSONBookmarkRepository": (
        "voice_reader.infrastructure.bookmarks.json_bookmark_repository",
        "JSONBookmarkRepository",
    ),
    "JSONIdeaIndexRepository": (
        "voice_reader.infrastructure.ideas.json_idea_index_repository",
        "JSONIdeaIndexRepository",
    ),
    "JSONPreferencesRepository": (
        "voice_reader.infrastructure.preferences.json_preferences_repository",
        "JSONPreferencesRepository",
    ),
    "KokoroVoiceProfileRepository": (
        "voice_reader.infrastructure.tts.voice_profile_repository",
        "KokoroVoiceProfileRepository",
    ),
    "FileSystemWalker": (
        "voice_reader.infrastructure.shelf.walker",
        "FileSystemWalker",
    ),
    "ShelfMetadataReader": (
        "voice_reader.infrastructure.shelf.metadata_reader",
        "ShelfMetadataReader",
    ),
    "SqliteShelfIndex": (
        "voice_reader.infrastructure.shelf.index_store",
        "SqliteShelfIndex",
    ),
    "FileThumbnailStore": (
        "voice_reader.infrastructure.shelf.thumbnails",
        "FileThumbnailStore",
    ),
    "ShelfCoverReader": (
        "voice_reader.infrastructure.shelf.cover_reader",
        "ShelfCoverReader",
    ),
    "QtThumbnailMaker": (
        "voice_reader.infrastructure.shelf.thumbnailer",
        "QtThumbnailMaker",
    ),
    # UI layer
    "MainWindow": ("voice_reader.ui.main_window", "MainWindow"),
    "UiController": ("voice_reader.ui.ui_controller", "UiController"),
    "install_update_check": ("voice_reader.ui.update_check", "install_update_check"),
    # Child-process composition root (book loading off the UI process).
    "load_book_in_subprocess": (
        "voice_reader.book_load_worker",
        "load_in_subprocess",
    ),
}


def install_wiring_placeholders(target_globals: dict[str, object]) -> None:
    """Define every wiring name up front, set to None.

    Unit tests monkeypatch these names on the entrypoint module to avoid the
    heavy imports; monkeypatching is only stable if the name already exists.
    The real imports still happen lazily inside `main()`.

    The names come from the same table `resolve_app_wiring` fills, so the
    placeholders cannot drift away from the wiring they stand in for.
    """

    for sym in _APP_WIRING_IMPORTS:
        target_globals.setdefault(sym, None)


def resolve_app_wiring(
    target_globals: dict[str, object],
    tick_fn: Callable[[], None] | None = None,
) -> None:
    """Populate missing app wiring symbols into an entrypoint's globals.

    Unit tests often monkeypatch these names on the entrypoint module to avoid
    importing heavy runtime dependencies. This helper respects those patches by
    only setting names that are currently missing/None.

    Args:
        target_globals: The module globals dict to populate.
        tick_fn: Optional callable invoked after each module import.  Pass
            ``app.processEvents`` to keep the Qt event loop alive during the
            heavy import phase and prevent the GNOME "not responding" dialog.
    """

    for sym, (mod, attr) in _APP_WIRING_IMPORTS.items():
        if target_globals.get(sym) is not None:
            continue
        m = importlib.import_module(mod)
        target_globals[sym] = getattr(m, attr)
        if tick_fn is not None:
            try:
                tick_fn()
            except Exception:
                pass


@dataclass(frozen=True, slots=True)
class Shelf:
    """The three shelf collaborators an entrypoint hands to the UI.

    They are returned together because they are one feature and are always
    wired together; returning a tuple of three would let a caller put them in
    the wrong order without the interpreter noticing.
    """

    scanner: object
    library: object
    thumbnails: object
    covers: object


def build_shelf(
    resolve: Callable[[str], object],
    *,
    index_dir: Path,
    thumbnails_dir: Path,
    bookmark_repo: object,
) -> Shelf:
    """Wire the shelf's real infrastructure behind its four ports.

    `resolve` answers a wiring name from the table above, so this helper holds
    no import of its own and the infrastructure classes stay lazy exactly as
    the rest of the wiring does.

    The two directories arrive rather than being derived here: where the index
    and the thumbnails live is the configuration's statement (DATA-BS-003); a
    second derivation here could disagree with it.
    """

    index = resolve("SqliteShelfIndex")(directory=index_dir)
    scanner = resolve("ShelfScanner")(
        walker=resolve("FileSystemWalker")(),
        metadata=resolve("ShelfMetadataReader")(),
        index=index,
    )
    library = resolve("ShelfLibrary")(index=index, bookmarks=bookmark_repo)
    thumbnails = resolve("FileThumbnailStore")(directory=thumbnails_dir)
    covers = resolve("ShelfCovers")(
        covers=resolve("ShelfCoverReader")(),
        thumbnails=thumbnails,
        maker=resolve("QtThumbnailMaker")(),
    )
    return Shelf(scanner=scanner, library=library, thumbnails=thumbnails, covers=covers)


# Everything the narration stack is built with. Each was a literal in the
# entrypoint before the services moved here; they are named rather than inlined
# so a reader can see what the number is for.
_NARRATION_DEVICE = "cpu"
_AUDIO_BUFFER_SECONDS = 15.0
_CHUNK_MIN_CHARS = 120
_CHUNK_MAX_CHARS = 220


@dataclass(frozen=True, slots=True)
class AppServices:
    """The application assembled: what the window and the controller need.

    One object rather than a dozen locals in the entrypoint, so the wiring can
    be built and read in one place and the entrypoint stays short enough to
    take in at a glance.
    """

    narration_service: object
    bookmark_service: object
    idea_map_service: object
    idea_indexing_manager: object
    structural_bookmark_service: object
    voice_service: object
    preferences_repo: object
    device: str
    engine_name: str
    shelf: Shelf


def build_services(resolve: Callable[[str], object], config: object) -> AppServices:
    """Construct every service the window is driven by, in dependency order.

    `resolve` answers a wiring name, which is how the entrypoint's own
    monkeypatched names still win in a test: nothing here imports a module
    directly.
    """

    paths = config.paths
    converter = resolve("CalibreConverter")(temp_books_dir=paths.temp_books_dir)
    parser = resolve("BookParser")()
    book_repo = resolve("LocalBookRepository")(converter=converter, parser=parser)
    cache_repo = resolve("FilesystemCacheRepository")(cache_dir=paths.cache_dir)

    bookmark_repo = resolve("JSONBookmarkRepository")(bookmarks_dir=paths.bookmarks_dir)
    bookmark_service = resolve("BookmarkService")(repo=bookmark_repo)

    idea_repo = resolve("JSONIdeaIndexRepository")(bookmarks_dir=paths.bookmarks_dir)

    preferences_repo = resolve("JSONPreferencesRepository")(path=paths.preferences_path)
    voice_service = resolve("VoiceProfileService")(
        repo=resolve("KokoroVoiceProfileRepository")()
    )

    tts_engine = resolve("TTSEngineFactory")().create()
    narration_service = resolve("NarrationService")(
        book_repo=book_repo,
        cache_repo=cache_repo,
        tts_engine=tts_engine,
        audio_streamer=resolve("SoundDeviceAudioStreamer")(
            target_buffer_seconds=_AUDIO_BUFFER_SECONDS
        ),
        chunking_service=resolve("ChunkingService")(
            min_chars=_CHUNK_MIN_CHARS, max_chars=_CHUNK_MAX_CHARS
        ),
        device=_NARRATION_DEVICE,
        language=config.default_language,
        bookmark_service=bookmark_service,
        preferences_repo=preferences_repo,
    )

    return AppServices(
        narration_service=narration_service,
        bookmark_service=bookmark_service,
        idea_map_service=resolve("IdeaMapService")(repo=idea_repo),
        idea_indexing_manager=resolve("IdeaIndexingManager")(repo=idea_repo),
        structural_bookmark_service=resolve("StructuralBookmarkService")(),
        voice_service=voice_service,
        preferences_repo=preferences_repo,
        device=_NARRATION_DEVICE,
        engine_name=tts_engine.engine_name,
        shelf=build_shelf(
            resolve,
            index_dir=paths.shelf_index_dir,
            thumbnails_dir=paths.shelf_thumbnails_dir,
            bookmark_repo=bookmark_repo,
        ),
    )


def wiring_module_names() -> tuple[str, ...]:
    """Every module the entrypoint resolves dynamically, for packagers.

    PyInstaller cannot see through `importlib.import_module`, so the build
    scripts declare each wiring module as a hidden import. They derive the
    list from here rather than mirroring it by hand, because a mirrored
    list silently drifts the first time an entry is added (the frozen app
    then dies at startup with ModuleNotFoundError while the dev run works).
    """

    return tuple(sorted({mod for mod, _attr in _APP_WIRING_IMPORTS.values()}))


def _touch() -> None:
    """Coverage helper.

    This module will be fleshed out as wiring moves from UI into the composition root.
    Keeping a tiny function makes it trivial to cover under the existing 100% gate.
    """

    return
