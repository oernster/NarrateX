"""Domain entity: TextChunk."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_id: int
    text: str
    start_char: int
    end_char: int
