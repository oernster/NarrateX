"""UiController state->UI application.

Separated to keep the main controller file small.
"""

from __future__ import annotations

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.chapter_progress import chapter_progress_label
from voice_reader.ui._ui_controller_chapters import apply_chapter_controls


def _apply_progress_label(controller, state: NarrationState) -> None:
    """Name the chapter being read, falling back to the fragment count.

    The fallback is for a book with no chapters at all, where there is nothing
    better to say. Everything else reports the chapter, because "1847/3200"
    counts pieces of machinery rather than anything the listener asked about.
    """

    label: str | None = None
    try:
        _, char_offset = controller.narration_service.current_position()
        book = controller.narration_service.loaded_book()
        label = chapter_progress_label(
            getattr(controller, "_chapters", []) or [],
            char_offset=char_offset,
            book_length=len(getattr(book, "normalized_text", "") or ""),
        )
    except Exception:
        label = None

    if label is None and state.total_chunks:
        label = f"{(state.current_chunk_id or 0) + 1}/{state.total_chunks}"

    if label is None:
        return

    try:
        controller.window.lbl_progress.setText(label)
    except Exception:
        pass


def on_state(controller, state: NarrationState) -> None:
    try:
        controller.state_received.emit(state)
    except RuntimeError:
        return


def apply_state(controller, state: object) -> None:
    if not isinstance(state, NarrationState):
        return

    # Drive unified Play/Pause transport button (presentation only).
    try:
        if hasattr(controller.window, "set_transport_playing"):
            # Note: NarrationService can emit SYNTHESIZING updates while audio is
            # actively playing (prefetch running ahead). For transport affordances,
            # treat the whole active pipeline as "pause-able".
            active_statuses = {
                NarrationStatus.LOADING,
                NarrationStatus.CHUNKING,
                NarrationStatus.SYNTHESIZING,
                NarrationStatus.PLAYING,
            }
            controller.window.set_transport_playing(
                is_playing=state.status in active_statuses
            )
    except Exception:
        pass

    # Book switching must be disabled during active playback/preparation.
    # Re-enable on PAUSED/STOPPED/IDLE/ERROR.
    book_select_locked_statuses = {
        NarrationStatus.LOADING,
        NarrationStatus.CHUNKING,
        NarrationStatus.SYNTHESIZING,
        NarrationStatus.PLAYING,
    }
    select_book_locked = state.status in book_select_locked_statuses
    try:
        btn = getattr(controller.window, "btn_select_book", None)
        if btn is not None:
            btn.setEnabled(not select_book_locked)
            btn.setProperty("selectBookLocked", bool(select_book_locked))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
    except Exception:
        pass

    _apply_progress_label(controller, state)

    try:
        if hasattr(controller.window, "lbl_status"):
            controller.window.lbl_status.setText(state.message or state.status.value)
    except Exception:
        pass

    try:
        # Use an animated indeterminate bar (sliding fill, not a spinner) while
        # waiting for the first audio chunk before playback has begun.  Switch
        # back to a real percentage bar the moment any chunk starts playing.
        pre_playback_synth = (
            state.status == NarrationStatus.SYNTHESIZING
            and state.playback_chunk_id is None
        )
        if pre_playback_synth:
            controller.window.progress.setRange(0, 0)
        else:
            controller.window.progress.setRange(0, 100)
            controller.window.progress.setValue(int(state.progress * 100))
    except Exception:
        pass

    # Lock voice + speed only (volume must remain editable).
    editable_statuses = {
        NarrationStatus.IDLE,
        NarrationStatus.PAUSED,
        NarrationStatus.STOPPED,
        NarrationStatus.ERROR,
    }
    locked = state.status not in editable_statuses
    for combo in (
        getattr(controller.window, "voice_combo", None),
        getattr(controller.window, "speed_combo", None),
    ):
        if combo is None:
            continue
        try:
            combo.setEnabled(not locked)
            combo.setProperty("locked", bool(locked))
            combo.style().unpolish(combo)
            combo.style().polish(combo)
        except Exception:
            pass

    start = state.audible_start
    end = state.audible_end
    if start is None or end is None:
        start = state.highlight_start
        end = state.highlight_end

    # Drive the chapter spine playhead from the audible start position.
    # Keep the last seen playhead even when paused/stopped; only clear on book switch.
    try:
        if hasattr(controller.window, "chapter_spine"):
            controller.window.chapter_spine.set_playhead_char_offset(start)
    except Exception:
        pass
    try:
        controller.window.highlight_range(start, end)
    except Exception:
        pass

    if start is not None:
        try:
            apply_chapter_controls(controller, current_char_offset=int(start))
        except Exception:
            pass
