"""Domain interface: audio cache repository."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CacheRepository(Protocol):
    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path: ...

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool: ...

    def ensure_parent_dir(self, path: Path) -> None: ...

    # Alignment cache lives alongside the WAV cache.
    def alignment_path(
        self, *, book_id: str, voice_name: str, chunk_id: int
    ) -> Path: ...

    def alignment_exists(
        self, *, book_id: str, voice_name: str, chunk_id: int
    ) -> bool: ...

    def purge_book(self, *, book_id: str) -> None:
        """Delete every cached artefact for one book (audio and alignment)."""
