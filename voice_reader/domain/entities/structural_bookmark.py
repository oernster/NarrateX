"""Domain entity: StructuralBookmark.

Structural bookmarks are deterministic, read-only section landmarks derived from
the already-loaded book content.

This concept is intentionally separate from manual bookmarks:
- not persisted
- not used for resume position
- not written into bookmarks JSON
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StructuralBookmark:
    """A deterministic section landmark derived from book structure."""

    label: str
    # Canonical anchor into the normalized book text.
    char_offset: int
    # Optional playback candidate index; may be resolved lazily.
    chunk_index: int | None
    # Kind label used for filtering/UX (e.g. "chapter", "part").
    kind: str
    # Reserved for future indentation (e.g. Part > Chapter). Initial UI is flat.
    level: int = 0

