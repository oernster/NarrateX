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


def forget_current_book(service: NarrationService) -> str | None:
    """Delete the service's memory of the loaded book, never the file.

    Stops playback WITHOUT persisting a resume position, purges the cached
    narration audio, deletes the bookmark file (bookmarks plus resume),
    forgets the last-book preference so the book is not auto-loaded next
    run, then unloads. Returns the removed book id, or None when nothing
    was loaded. The caller owns the ideas index (it holds that service).
    """

    book = service._book  # noqa: SLF001
    if book is None:
        return None
    book_id = str(book.id)

    # The audio cache is keyed by the derived cache id, which needs the
    # book still loaded, so compute it before anything is torn down.
    try:
        from voice_reader.application.services.narration.cache_key import (
            compute_book_cache_id,
        )

        cache_id = compute_book_cache_id(service)
    except Exception:
        cache_id = None

    try:
        service.stop(persist_resume=False)
    except Exception:
        pass

    if cache_id is not None:
        try:
            service.cache_repo.purge_book(book_id=cache_id)
        except Exception:
            pass

    if service.bookmark_service is not None:
        try:
            service.bookmark_service.delete_book_state(book_id=book_id)
        except Exception:
            pass

    if service.preferences_repo is not None:
        try:
            service.preferences_repo.clear_last_book_path()
        except Exception:
            pass

    service._book = None  # noqa: SLF001
    service._chunks = []  # noqa: SLF001
    service._start_char = None  # noqa: SLF001
    service._cache_book_id = None  # noqa: SLF001

    service._set_state(  # noqa: SLF001
        NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message=f"Removed '{book.title}' (the file is kept)",
        )
    )
    return book_id
