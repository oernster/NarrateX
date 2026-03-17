"""UiController state->UI application.

Separated to keep the main controller file small.
"""

from __future__ import annotations

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.ui._ui_controller_chapters import apply_chapter_controls


def on_state(controller, state: NarrationState) -> None:
    try:
        controller.state_received.emit(state)
    except RuntimeError:
        return


def apply_state(controller, state: object) -> None:
    if not isinstance(state, NarrationState):
        return

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

    if state.total_chunks:
        try:
            controller.window.lbl_progress.setText(
                f"{(state.current_chunk_id or 0) + 1}/{state.total_chunks}"
            )
        except Exception:
            pass

    try:
        if hasattr(controller.window, "lbl_status"):
            controller.window.lbl_status.setText(state.message or state.status.value)
    except Exception:
        pass

    try:
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
