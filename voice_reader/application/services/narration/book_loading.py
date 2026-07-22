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


def _begin_load(service: NarrationService, source_path: Path) -> None:
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


def _finish_load(service: NarrationService, book: "Book", source_path: Path) -> "Book":
    service._book = book  # noqa: SLF001
    service._start_char = None  # noqa: SLF001
    service._cache_book_id = None  # noqa: SLF001

    if service.preferences_repo is not None:
        try:
            service.preferences_repo.save_last_book_path(source_path)
        except Exception:
            pass

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


def load_book(service: NarrationService, source_path: Path) -> "Book":
    _begin_load(service, source_path)
    book = service.book_repo.load(source_path)
    return _finish_load(service, book, source_path)


def adopt_book(service: NarrationService, book: "Book", source_path: Path) -> "Book":
    """Take ownership of an already-parsed book without re-parsing it.

    The book-load worker process does the expensive parse; this is the
    parent-side half, which is everything `load_book` does around the parse.
    """

    _begin_load(service, source_path)
    return _finish_load(service, book, source_path)
