from __future__ import annotations

from typing import TYPE_CHECKING

from voice_reader.application.services.narration.prepare import (
    resolve_playback_index_for_char_offset,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def maybe_save_resume_position(service: NarrationService) -> None:
    if not bool(getattr(service, "_persist_resume", True)):
        return
    if service.bookmark_service is None:
        return
    if service._book is None:  # noqa: SLF001
        return

    # User requirement: do not create a resume JSON unless playback has actually
    # started at least one chunk.
    #
    # Primary signal: runtime flag flipped by audio playback callbacks.
    played_any = bool(getattr(service, "_played_any_chunk", False))
    # Secondary signal (testability + resilience): infer from state when the
    # callback could not fire (e.g. app exit races, paused sessions).
    if not played_any:
        try:
            st = service.state
            played_any = bool(
                st.audible_start is not None
                or st.highlight_start is not None
                or st.playback_chunk_id is not None
                or (
                    st.status.name in {"PLAYING", "PAUSED"}
                    and st.current_chunk_id is not None
                )
            )
        except Exception:
            played_any = False

    if not played_any:
        return

    # Prefer the most precise stable anchor we have: the current audible/highlight
    # char offset (absolute book coordinates).
    st = service.state
    char_offset = st.audible_start
    if char_offset is None:
        char_offset = st.highlight_start

    if char_offset is None:
        # Fall back to the older logic (may still return None if state is empty).
        chunk_index, char_offset = service.current_position()
        if chunk_index is None or char_offset is None:
            # Last-resort: if playback started but state did not update in time,
            # persist the first available chunk start. This guarantees a JSON
            # file exists after real playback.
            try:
                if service._chunks:  # noqa: SLF001
                    chunk_index = 0
                    char_offset = int(service._chunks[0].start_char)  # noqa: SLF001
            except Exception:
                chunk_index, char_offset = None, None
            if chunk_index is None or char_offset is None:
                return
    else:
        # Compute a candidate-list chunk_index consistent with playback semantics.
        try:
            idx = resolve_playback_index_for_char_offset(
                service,
                char_offset=int(char_offset),
                chunks=service._chunks,  # noqa: SLF001
            )
        except Exception:
            idx = None
        chunk_index = 0 if idx is None else int(idx)

    try:
        service.bookmark_service.save_resume_position(
            book_id=service._book.id,  # noqa: SLF001
            char_offset=int(char_offset),
            chunk_index=int(chunk_index),
        )
    except Exception:
        # Resume persistence must never break playback.
        service._log.exception("Failed saving resume position")  # noqa: SLF001
