"""Composition root helper.

This module exists to keep entrypoints small while still making wiring explicit.

Hard rule enforced by structural tests:
- Only entrypoints (e.g. [`main()`](app.py:176) and installer entrypoints) may
  import [`voice_reader.bootstrap`](voice_reader/bootstrap.py:1).
- Other modules must not depend on this module.
"""

from __future__ import annotations

import importlib
from typing import Mapping


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
    "StructuralBookmarkService": (
        "voice_reader.application.services.structural_bookmark_service",
        "StructuralBookmarkService",
    ),
    "VoiceProfileService": (
        "voice_reader.application.services.voice_profile_service",
        "VoiceProfileService",
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
    # UI layer
    "MainWindow": ("voice_reader.ui.main_window", "MainWindow"),
    "UiController": ("voice_reader.ui.ui_controller", "UiController"),
}


def resolve_app_wiring(target_globals: dict[str, object]) -> None:
    """Populate missing app wiring symbols into an entrypoint's globals.

    Unit tests often monkeypatch these names on the entrypoint module to avoid
    importing heavy runtime dependencies. This helper respects those patches by
    only setting names that are currently missing/None.
    """

    for sym, (mod, attr) in _APP_WIRING_IMPORTS.items():
        if target_globals.get(sym) is not None:
            continue
        m = importlib.import_module(mod)
        target_globals[sym] = getattr(m, attr)


def _touch() -> None:
    """Coverage helper.

    This module will be fleshed out as wiring moves from UI into the composition root.
    Keeping a tiny function makes it trivial to cover under the existing 100% gate.
    """

    return
