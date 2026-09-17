"""UiController chapter navigation and chapter-UI updates.

A chapter button is enabled exactly when pressing it would move somewhere.
`chapter_target` is the one answer to that question: the jump uses it to decide
where to go and the availability uses it to decide whether the button is live,
so a button can never look ready while doing nothing. Measured before this was
so: after Stop the narration has no position, the jump quietly returned and
both buttons still wore the green ring of a control that works.
"""

from __future__ import annotations

_DIRECTIONS = ("previous", "next")


def chapter_target(controller, *, direction: str):
    """The chapter a press would move to; None when a press would do nothing.

    Nothing happens without chapters, without a current position (Stop and a
    freshly loaded book have none; Pause keeps one), without a chapter in that
    direction or without a chosen voice to narrate it.
    """

    chapters = getattr(controller, "_chapters", None)
    if not chapters:
        return None
    try:
        _chunk, char_offset = controller.narration_service.current_position()
    except Exception:
        return None
    if char_offset is None:
        return None

    service = controller._chapter_index_service  # noqa: SLF001
    find = (
        service.get_previous_chapter
        if direction == "previous"
        else service.get_next_chapter
    )
    target = find(chapters, current_char_offset=int(char_offset))
    if target is None or controller._selected_voice() is None:  # noqa: SLF001
        return None
    return target


def refresh_chapter_availability(controller) -> None:
    """Enable each chapter button only when pressing it would act."""

    previous, next_ = (
        chapter_target(controller, direction=d) is not None for d in _DIRECTIONS
    )
    try:
        controller.window.set_chapter_controls_enabled(previous=previous, next_=next_)
    except Exception:
        pass


def apply_chapter_controls(controller, *, current_char_offset: int) -> None:
    """Point the spine at the chapter holding the offset; refresh the buttons."""

    chapters = getattr(controller, "_chapters", None)
    current = None
    if chapters:
        current = controller._chapter_index_service.get_current_chapter(  # noqa: SLF001
            chapters,
            current_char_offset=int(current_char_offset),
        )
    controller._current_chapter = current  # noqa: SLF001
    refresh_chapter_availability(controller)
    try:
        if hasattr(controller.window, "chapter_spine"):
            controller.window.chapter_spine.set_current_chapter(current)
    except Exception:
        pass


def previous_chapter(controller) -> None:
    jump_to_chapter(controller, direction="previous")


def next_chapter(controller) -> None:
    jump_to_chapter(controller, direction="next")


def jump_to_chapter(controller, *, direction: str) -> None:
    target = chapter_target(controller, direction=direction)
    if target is None:
        return

    voice = controller._selected_voice()  # noqa: SLF001

    try:
        controller.narration_service.stop()
    except Exception:
        pass

    controller._last_prepared_voice_id = voice.name  # noqa: SLF001
    controller.narration_service.prepare(
        voice=voice,
        start_playback_index=int(target.chunk_index),
    )
    controller.narration_service.start()

    try:
        apply_chapter_controls(controller, current_char_offset=int(target.char_offset))
    except Exception:
        pass
