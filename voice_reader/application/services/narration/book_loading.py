from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration.persistence import (
    maybe_save_resume_position,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.book import Book


def load_book(service: NarrationService, source_path: Path) -> "Book":
    maybe_save_resume_position(service)
    service._persist_resume = True  # noqa: SLF001

    try:
        service.stop()
    except Exception:
        pass

    service._set_state(
        NarrationState(
            status=NarrationStatus.LOADING,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message=f"Loading {source_path.name}...",
        )
    )

    book = service.book_repo.load(source_path)
    service._book = book  # noqa: SLF001
    service._start_char = None  # noqa: SLF001
    service._cache_book_id = None  # noqa: SLF001
    service._set_state(
        NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message=f"Loaded '{book.title}'",
        )
    )
    return book
