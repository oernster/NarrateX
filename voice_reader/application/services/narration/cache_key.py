from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def compute_book_cache_id(service: NarrationService) -> str:
    """Return a stable cache key used by the audio/alignment repositories."""

    if service._cache_book_id is not None:  # noqa: SLF001 (internal state)
        return service._cache_book_id

    if service._book is None:  # noqa: SLF001
        raise ValueError("Book not loaded")

    if service._start_char is None:  # noqa: SLF001
        start = service.reading_start_detector.detect_start(
            service._book.normalized_text
        )
        service._start_char = start.start_char

    # Bump version when changing audio-affecting logic.
    version_tag = "v14"
    engine_tag = service.tts_engine.engine_name.strip().lower()
    payload = (
        f"{service._book.normalized_text}|"  # noqa: SLF001
        f"start={service._start_char}|"  # noqa: SLF001
        f"engine={engine_tag}|"
        f"{version_tag}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    service._cache_book_id = digest[:16]
    return service._cache_book_id
