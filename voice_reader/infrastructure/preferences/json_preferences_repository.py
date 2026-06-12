"""JSON-backed user preferences persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


@dataclass(frozen=True, slots=True)
class JSONPreferencesRepository(PreferencesRepository):
    """Persist simple preferences to a small JSON file."""

    path: Path

    def _load_raw(self) -> dict:
        try:
            if not self.path.exists():
                return {}
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_raw(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_playback_volume(self) -> PlaybackVolume | None:
        try:
            v = float(self._load_raw().get("playback_volume", None))
        except Exception:
            return None
        try:
            return PlaybackVolume(v)
        except Exception:
            return None

    def save_playback_volume(self, volume: PlaybackVolume) -> None:
        data = self._load_raw()
        data["playback_volume"] = float(volume.multiplier)
        self._save_raw(data)

    def load_last_book_path(self) -> Path | None:
        try:
            raw = self._load_raw().get("last_book_path")
            if not raw:
                return None
            p = Path(str(raw))
            return p if p.exists() else None
        except Exception:
            return None

    def save_last_book_path(self, path: Path) -> None:
        data = self._load_raw()
        data["last_book_path"] = str(path)
        self._save_raw(data)
