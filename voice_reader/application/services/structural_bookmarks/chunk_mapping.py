from __future__ import annotations

from typing import Sequence

from voice_reader.domain.entities.text_chunk import TextChunk


def resolve_char_offset_for_chunk_index(
    *,
    chunk_index: int,
    chunks: Sequence[TextChunk] | None,
) -> int | None:
    if not chunks:
        return None
    try:
        idx = int(chunk_index)
    except Exception:
        return None
    if idx < 0 or idx >= len(chunks):
        return None
    try:
        return int(chunks[idx].start_char)
    except Exception:
        return None


def resolve_chunk_index_for_offset(
    *,
    char_offset: int,
    chunks: Sequence[TextChunk] | None,
) -> int | None:
    if not chunks:
        return None
    try:
        off = int(char_offset)
    except Exception:
        return None

    for idx, c in enumerate(chunks):
        try:
            if int(c.start_char) <= off < int(c.end_char):
                return int(idx)
            if int(c.start_char) >= off:
                return int(idx)
        except Exception:
            continue
    return None
