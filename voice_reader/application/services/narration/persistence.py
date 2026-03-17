from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def maybe_save_resume_position(service: NarrationService) -> None:
    if not bool(getattr(service, "_persist_resume", True)):
        return
    if service.bookmark_service is None:
        return
    if service._book is None:  # noqa: SLF001
        return
    chunk_index, char_offset = service.current_position()
    if chunk_index is None or char_offset is None:
        return
    try:
        service.bookmark_service.save_resume_position(
            book_id=service._book.id,  # noqa: SLF001
            char_offset=int(char_offset),
            chunk_index=int(chunk_index),
        )
    except Exception:
        # Resume persistence must never break playback.
        service._log.exception("Failed saving resume position")  # noqa: SLF001
