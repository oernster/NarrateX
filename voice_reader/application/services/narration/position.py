from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def current_position(service: NarrationService) -> tuple[int | None, int | None]:
    st = service.state

    rel_idx = st.playback_chunk_id
    if rel_idx is None:
        rel_idx = st.current_chunk_id
    if rel_idx is None:
        return None, None

    chunk_index = int(service._start_playback_index) + int(rel_idx)  # noqa: SLF001

    char_offset = st.audible_start
    if char_offset is None:
        char_offset = st.highlight_start
    if char_offset is None:
        try:
            char_offset = int(
                service._chunks[int(chunk_index)].start_char
            )  # noqa: SLF001
        except Exception:
            char_offset = None

    return chunk_index, char_offset
