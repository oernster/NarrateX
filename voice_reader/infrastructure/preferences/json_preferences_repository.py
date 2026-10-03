"""JSON-backed user preferences persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.interfaces.preferences_repository import PreferencesRepository
from voice_reader.domain.shelf import layout as layout_rules
from voice_reader.domain.shelf.layout import ShelfLayout
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume
from voice_reader.infrastructure import json_document


@dataclass(frozen=True, slots=True)
class JSONPreferencesRepository(PreferencesRepository):
    """Persist simple preferences to a small JSON file.

    Reads are tolerant: a missing, damaged or unreadable file reads as the
    defaults and is left exactly as it was. A save never writes over damage:
    it keeps a damaged file aside as `preferences.json.damaged` first and
    refuses when the file cannot be read at all. Writes replace the file whole
    through a temporary, so an interrupted save leaves the old one.
    """

    path: Path

    def _load_raw(self) -> dict:
        try:
            return json_document.read_object(self.path) or {}
        except (OSError, json_document.DamagedDocumentError):
            return {}

    def _load_for_update(self) -> dict:
        return json_document.object_for_update(self.path)

    def _save_raw(self, data: dict) -> None:
        json_document.write_object(self.path, data, sort_keys=True)

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
        data = self._load_for_update()
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
        data = self._load_for_update()
        data["last_book_path"] = str(path)
        self._save_raw(data)

    def clear_last_book_path(self) -> None:
        data = self._load_for_update()
        if "last_book_path" in data:
            del data["last_book_path"]
            self._save_raw(data)

    def load_skipped_update_version(self) -> str | None:
        raw = self._load_raw().get("skipped_update_version")
        return raw if isinstance(raw, str) and raw else None

    def save_skipped_update_version(self, version: str) -> None:
        data = self._load_for_update()
        data["skipped_update_version"] = version
        self._save_raw(data)

    def load_shelf_layout(self) -> ShelfLayout | None:
        return layout_rules.parsed(self._load_raw().get("shelf_layout"))

    def save_shelf_layout(self, layout: ShelfLayout) -> None:
        data = self._load_for_update()
        data["shelf_layout"] = layout.value
        self._save_raw(data)
