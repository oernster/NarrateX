from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawHeadingCandidate:
    label: str
    char_offset: int | None
    chunk_index: int | None
    source: str  # "nav" | "chapter_parser" | "text_scan" | ...


@dataclass(frozen=True, slots=True)
class HeadingOccurrence:
    char_offset: int
    label: str
    prev_blank: bool
    next_blank: bool
