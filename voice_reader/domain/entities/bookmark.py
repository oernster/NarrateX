"""Domain entities: bookmarks.

In v1 we support:

- One hidden resume position per book.
- Multiple manual bookmarks per book.

Bookmarks are anchored by a stable character offset into the normalized book text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Bookmark:
    bookmark_id: int
    name: str
    char_offset: int
    chunk_index: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResumePosition:
    char_offset: int
    chunk_index: int
    updated_at: datetime
