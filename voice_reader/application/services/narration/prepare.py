from __future__ import annotations

from typing import TYPE_CHECKING

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.domain.entities.text_chunk import TextChunk

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.voice_profile import VoiceProfile


def resolve_playback_index_for_char_offset(
    service: NarrationService,
    *,
    char_offset: int,
    chunks: list[TextChunk],
) -> int | None:
    """Map an absolute book char_offset to a playback candidate index.

    This must match candidate filtering used in `run`:
    candidates are chunks where sanitized speak_text is non-empty.
    """

    if not chunks:
        return None

    candidates: list[TextChunk] = []
    for c in chunks:
        mapped = service.sanitized_text_mapper.sanitize_with_mapping(
            original_text=c.text
        )
        if mapped.speak_text:
            candidates.append(c)

    if not candidates:
        return None

    for idx, c in enumerate(candidates):
        if int(c.start_char) <= int(char_offset) < int(c.end_char):
            return int(idx)
        if int(c.start_char) >= int(char_offset):
            return int(idx)
    return None


def prepare(
    service: NarrationService,
    *,
    voice: VoiceProfile,
    start_playback_index: int | None = None,
    start_char_offset: int | None = None,
    force_start_char: int | None = None,
    skip_essay_index: bool = True,
    persist_resume: bool = True,
) -> list[TextChunk]:
    if service._book is None:  # noqa: SLF001
        raise ValueError("Book not loaded")

    service._voice = voice  # noqa: SLF001

    # New run: clear any pending stop-at-boundary request.
    try:
        service._stop_after_current_chunk.clear()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass

    service._persist_resume = bool(persist_resume)  # noqa: SLF001

    if start_playback_index is None and start_char_offset is None:
        resume_idx: int | None = None
        if service.bookmark_service is not None:
            try:
                rp = service.bookmark_service.load_resume_position(
                    book_id=service._book.id  # noqa: SLF001
                )
            except Exception:
                rp = None
            if rp is not None:
                resume_idx = int(rp.chunk_index)
        service._start_playback_index = max(0, int(resume_idx or 0))  # noqa: SLF001
    elif start_playback_index is not None:
        service._start_playback_index = max(
            0, int(start_playback_index)
        )  # noqa: SLF001
    else:
        service._start_playback_index = 0  # noqa: SLF001

    # Reset play position tracking for the next run.
    service._current_play_index = -1  # noqa: SLF001

    assert service.navigation_chunk_service is not None
    chunks, start = service.navigation_chunk_service.build_chunks(
        book_text=service._book.normalized_text,  # noqa: SLF001
        force_start_char=force_start_char,
        skip_essay_index=bool(skip_essay_index),
    )
    service._start_char = int(start.start_char)  # noqa: SLF001
    service._cache_book_id = None  # noqa: SLF001

    service._set_state(
        NarrationState(
            status=NarrationStatus.CHUNKING,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message=f"Chunking text ({start.reason})...",
        )
    )

    service._chunks = list(chunks)  # noqa: SLF001

    # If we have an absolute start offset (e.g. Ideas Go To), we must ensure
    # playback begins from the first chunk containing/after that offset.
    if start_char_offset is not None:
        try:
            absolute = int(start_char_offset)
        except Exception:  # pragma: no cover
            absolute = None
        if absolute is not None and service._chunks:  # noqa: SLF001
            for i, c in enumerate(service._chunks):  # noqa: SLF001
                if int(c.start_char) <= absolute < int(c.end_char):
                    cut = max(0, absolute - int(c.start_char))
                    if cut:
                        service._chunks[i] = TextChunk(
                            chunk_id=int(c.chunk_id),
                            text=str(c.text)[cut:],
                            start_char=int(c.start_char) + int(cut),
                            end_char=int(c.end_char),
                        )
                    break
                if int(c.start_char) >= absolute:
                    break

    if start_char_offset is not None:
        idx = resolve_playback_index_for_char_offset(
            service,
            char_offset=int(start_char_offset),
            chunks=service._chunks,  # noqa: SLF001
        )
        if idx is not None:
            service._start_playback_index = max(0, int(idx))  # noqa: SLF001

    service._set_state(
        NarrationState(
            status=NarrationStatus.IDLE,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=len(service._chunks),  # noqa: SLF001
            progress=0.0,
            message=f"Prepared {len(service._chunks)} chunks",  # noqa: SLF001
        )
    )
    return list(service._chunks)  # noqa: SLF001
