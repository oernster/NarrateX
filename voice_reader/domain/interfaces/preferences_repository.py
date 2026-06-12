"""Domain interface for lightweight user preferences persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


class PreferencesRepository(Protocol):
    """Persist small user preferences across application runs."""

    def load_playback_volume(self) -> PlaybackVolume | None: ...

    def save_playback_volume(self, volume: PlaybackVolume) -> None: ...

    def load_last_book_path(self) -> Path | None: ...

    def save_last_book_path(self, path: Path) -> None: ...
