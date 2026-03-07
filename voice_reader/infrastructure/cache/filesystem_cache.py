"""Filesystem cache for chunk audio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.interfaces.cache_repository import CacheRepository


@dataclass(frozen=True, slots=True)
class FilesystemCacheRepository(CacheRepository):
    cache_dir: Path

    def audio_path(self, *, book_id: str, voice_name: str, chunk_id: int) -> Path:
        return self.cache_dir / book_id / voice_name / f"{int(chunk_id):06d}.wav"

    def exists(self, *, book_id: str, voice_name: str, chunk_id: int) -> bool:
        return self.audio_path(
            book_id=book_id, voice_name=voice_name, chunk_id=chunk_id
        ).exists()

    def ensure_parent_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
