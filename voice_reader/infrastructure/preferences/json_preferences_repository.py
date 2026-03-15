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

    def load_playback_volume(self) -> PlaybackVolume | None:
        try:
            if not self.path.exists():
                return None
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            return None

        try:
            v = float(data.get("playback_volume", None))
        except Exception:
            return None

        try:
            return PlaybackVolume(v)
        except Exception:
            return None

    def save_playback_volume(self, volume: PlaybackVolume) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "playback_volume": float(volume.multiplier),
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
