"""UiController click-to-seek handler.

This module is UI-layer orchestration (under `voice_reader.ui`) but contains no
direct Qt widget logic. It:

- resolves a clicked absolute char offset into a narration *playback candidate*
  index (chunk-relative seeking)
- restarts playback via the existing NarrationService prepare/start pipeline
- persists resume position immediately on click (product requirement)
"""

from __future__ import annotations

import logging

from voice_reader.application.services.narration.prepare import (
    resolve_playback_index_for_char_offset,
)


def seek_to_char_offset(controller, offset: int) -> None:
    """Resolve `offset` to a playback chunk and restart narration from there."""

    log = getattr(controller, "_log", logging.getLogger(__name__))

    try:
        off = int(offset)
    except Exception:
        return

    # Source of truth for click coordinates is the displayed (normalized) text.
    try:
        text = controller.window.reader.toPlainText()
    except Exception:
        text = ""

    if not text:
        return
    off = max(0, min(int(off), len(text)))

    nav = getattr(controller, "_navigation_chunk_service", None)  # noqa: SLF001
    if nav is None:
        return

    try:
        chunks, _start = nav.build_chunks(book_text=text, skip_essay_index=True)
    except Exception:
        log.exception("Failed building navigation chunks for click-to-seek")
        return
    if not chunks:
        return

    svc = controller.narration_service

    # Map click offset to a playback candidate index (skipping non-speakable chunks).
    try:
        idx = resolve_playback_index_for_char_offset(
            svc,
            char_offset=int(off),
            chunks=list(chunks),
        )
    except Exception:
        idx = None
    if idx is None:
        idx = 0

    # Find the concrete chunk span for immediate highlight + stable resume char_offset.
    candidates = []
    try:
        mapper = getattr(svc, "sanitized_text_mapper", None)
        if mapper is None:
            candidates = list(chunks)
        else:
            for c in chunks:
                mapped = mapper.sanitize_with_mapping(original_text=c.text)
                if getattr(mapped, "speak_text", ""):
                    candidates.append(c)
    except Exception:
        candidates = list(chunks)

    if not candidates:
        return

    idx = max(0, min(int(idx), len(candidates) - 1))
    target = candidates[int(idx)]
    target_start = int(getattr(target, "start_char", 0))
    target_end = int(getattr(target, "end_char", target_start))

    # Front matter behavior: if click is before the first narratable chunk, we
    # implicitly clamp to reading-start. (No re-chunking.)
    try:
        first_start = int(getattr(candidates[0], "start_char", 0))
    except Exception:
        first_start = 0
    if int(off) < int(first_start):
        try:
            controller.window.lbl_status.setText("Seek clamped to reading start")
        except Exception:
            pass

    voice = None
    try:
        voice = controller._selected_voice()  # noqa: SLF001
    except Exception:
        voice = None
    if voice is None:
        return

    # Stop current playback without persisting the old position; click-to-seek
    # immediately persists the new resume location instead.
    try:
        svc.stop(persist_resume=False)
    except TypeError:
        try:
            svc.stop()
        except Exception:
            pass
    except Exception:
        pass

    try:
        controller._last_prepared_voice_id = voice.name  # noqa: SLF001
    except Exception:
        pass

    try:
        svc.prepare(voice=voice, start_playback_index=int(idx), persist_resume=True)
    except Exception:
        log.exception("Failed preparing narration for click-to-seek")
        return

    # UX: immediate highlight/scroll while synthesis begins.
    try:
        controller.window.highlight_range(target_start, target_end)
    except Exception:
        pass

    try:
        svc.start()
    except Exception:
        log.exception("Failed starting narration after click-to-seek")
        return

    # Persist resume immediately (even before audio starts): product requirement.
    try:
        book_id = svc.loaded_book_id()
    except Exception:
        book_id = None
    if book_id:
        try:
            controller.bookmark_service.save_resume_position(
                book_id=str(book_id),
                char_offset=int(target_start),
                chunk_index=int(idx),
            )
        except Exception:
            log.exception("Failed persisting resume after click-to-seek")

