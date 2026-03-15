"""UiController playback-related handlers.

Extracted for file-size limits and separation of concerns.
"""

from __future__ import annotations

import logging

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


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
