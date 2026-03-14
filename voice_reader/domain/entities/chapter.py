"""Domain entity: Chapter.

Chapters are read-only navigation metadata derived from the loaded book text.
They are not persisted and are reconstructed on each book load.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chapter:
    title: str
    char_offset: int
    # Absolute playback index into the narration candidate list.
    chunk_index: int

