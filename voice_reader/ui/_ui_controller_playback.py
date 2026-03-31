"""UiController playback-related handlers.

Extracted for file-size limits and separation of concerns.
"""

from __future__ import annotations

import logging

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

from voice_reader.ui.structural_bookmarks_helpers import compute_structural_bookmarks


def set_speed(controller, text: str) -> None:
    log = getattr(controller, "_log", logging.getLogger(__name__))
    try:
        raw = str(text).strip().lower().replace("x", "")
        rate = PlaybackRate(float(raw))
    except Exception:
        log.debug("Ignoring invalid speed value: %r", text)
        return

    try:
        controller.narration_service.set_playback_rate(rate)
    except Exception:
        log.exception("Failed setting playback rate")


def set_volume(controller, value: int) -> None:
    """Set playback volume from a 0..100 UI slider value."""

    log = getattr(controller, "_log", logging.getLogger(__name__))
    try:
        v = int(value)
    except Exception:
        log.debug("Ignoring invalid volume value: %r", value)
        return
    v = max(0, min(100, v))
    vol = PlaybackVolume(v / 100.0)
    try:
        controller.narration_service.set_volume(vol)
    except Exception:
        log.exception("Failed setting volume")

    # Best-effort reflect on the UI control (without requiring full state storage).
    try:
        if hasattr(controller.window, "volume_slider"):
            if int(controller.window.volume_slider.value()) != int(v):
                controller.window.volume_slider.setValue(int(v))
    except Exception:
        pass


def play(controller) -> None:
    """Play button semantics.

    - If paused: resume (or restart from current chunk if voice changed)
    - If stopped/idle: (re)prepare and start
    - If already playing: no-op
    """

    start_playback_index: int | None = None
    st = getattr(controller.narration_service, "state", None)
    if isinstance(st, NarrationState):
        if st.status == NarrationStatus.PAUSED:
            voice = controller._selected_voice()  # noqa: SLF001
            if (
                voice is not None
                and controller._last_prepared_voice_id is not None  # noqa: SLF001
                and voice.name != controller._last_prepared_voice_id  # noqa: SLF001
            ):
                start_playback_index = int(st.current_chunk_id or 0)
                controller.narration_service.stop()
            else:
                controller.narration_service.resume()
                return
        if st.status == NarrationStatus.PLAYING:
            return

    voice = controller._selected_voice()  # noqa: SLF001
    if voice is None:
        controller._log.warning("No voice profiles available")  # noqa: SLF001
        return

    # If we're starting from scratch (no explicit index and no saved resume),
    # prefer the same deterministic first Section shown in the 🧠 dialog.
    if start_playback_index is None:
        try:
            book_id = controller.narration_service.loaded_book_id()
        except Exception:
            book_id = None

        has_resume = False
        if book_id:
            try:
                rp = controller.bookmark_service.load_resume_position(
                    book_id=str(book_id)
                )
            except Exception:
                rp = None
            has_resume = rp is not None

        if book_id and not has_resume:
            comp = compute_structural_bookmarks(controller)
            if comp is not None and comp.bookmarks:
                first = comp.bookmarks[0]
                try:
                    start_char_offset = int(first.char_offset)
                except Exception:
                    start_char_offset = None

                # Defensive: never start playback from a pre-boundary structural
                # bookmark (e.g. a PDF TOC duplicate). Prefer the computed safe
                # boundary instead, which is based on the reading-start detector.
                if (
                    start_char_offset is not None
                    and comp.min_char_offset is not None
                    and int(start_char_offset) < int(comp.min_char_offset)
                ):
                    start_char_offset = int(comp.min_char_offset)

                if start_char_offset is not None:
                    # Force chunking to begin exactly at the target.
                    controller._last_prepared_voice_id = voice.name  # noqa: SLF001
                    controller.narration_service.prepare(
                        voice=voice,
                        start_char_offset=int(start_char_offset),
                        force_start_char=int(start_char_offset),
                        skip_essay_index=True,
                    )
                    controller.narration_service.start()
                    return

    controller._last_prepared_voice_id = voice.name  # noqa: SLF001
    controller.narration_service.prepare(
        voice=voice,
        start_playback_index=start_playback_index,
    )
    controller.narration_service.start()


def pause(controller) -> None:
    controller.narration_service.pause()


def stop(controller) -> None:
    controller.narration_service.stop()


def toggle_play_pause(controller) -> None:
    """Unified Play/Pause button semantics.

    Presentation-layer consolidation: reuse the existing `play()` / `pause()`
    handlers and decide which to invoke based on the current narration state.
    """

    st = getattr(controller.narration_service, "state", None)
    if isinstance(st, NarrationState):
        # Transport should be pause-able across the whole active pipeline.
        # This avoids a "dead click" when state momentarily reports SYNTHESIZING
        # while audio is still playing (prefetch can race UI interaction).
        pauseable_statuses = {
            NarrationStatus.LOADING,
            NarrationStatus.CHUNKING,
            NarrationStatus.SYNTHESIZING,
            NarrationStatus.PLAYING,
        }
        if st.status in pauseable_statuses:
            return pause(controller)
    return play(controller)
