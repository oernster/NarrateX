from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from pathlib import Path

from voice_reader.application.dto.narration_state import NarrationState
from voice_reader.domain.entities.voice_profile import VoiceProfile


@dataclass
class FakeNarration:
    listeners: list
    state: NarrationState
    last_rate: float | None = None
    last_volume: float | None = None

    def add_listener(self, listener):
        self.listeners.append(listener)

    def load_book(self, path: Path):
        del path
        return SimpleNamespace(normalized_text="Hello", title="T")

    def prepare(
        self,
        *,
        voice,
        start_playback_index=None,
        start_char_offset=None,
        force_start_char=None,
        skip_essay_index=True,
        persist_resume=True,
    ):
        del voice, start_playback_index
        del start_char_offset, force_start_char, skip_essay_index, persist_resume

    def start(self):
        return

    def pause(self):
        return

    def stop(self):
        return

    def set_playback_rate(self, rate) -> None:
        # Accept a PlaybackRate-ish object (value object in real code).
        self.last_rate = float(getattr(rate, "multiplier", rate))

    def set_volume(self, volume) -> None:
        self.last_volume = float(getattr(volume, "multiplier", volume))

    def loaded_book_id(self):
        return "b1"

    def current_position(self):
        return 0, 0

    def _maybe_save_resume_position(self):
        return


@dataclass
class FakeBookmarks:
    def list_bookmarks(self, *, book_id: str):
        del book_id
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        del book_id, char_offset, chunk_index
        return None

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        del book_id, bookmark_id

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        del book_id, char_offset, chunk_index

    def load_resume_position(self, *, book_id: str):
        del book_id
        return None


@dataclass(frozen=True, slots=True)
class FakeVoiceRepo:
    profiles: list[VoiceProfile]

    def list_profiles(self):
        return list(self.profiles)


@dataclass
class FakeIdeasRepo:
    doc: dict | None

    def load_doc(self, *, book_id: str):
        del book_id
        return self.doc

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        del book_id, doc
