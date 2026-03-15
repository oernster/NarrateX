"""UiController chapter navigation and chapter-UI updates."""

from __future__ import annotations


def apply_chapter_controls(controller, *, current_char_offset: int) -> None:
    if not controller._chapters:  # noqa: SLF001
        controller._current_chapter = None  # noqa: SLF001
        try:
            controller.window.set_chapter_controls_enabled(previous=False, next_=False)
        except Exception:
            pass
        try:
            if hasattr(controller.window, "chapter_spine"):
                controller.window.chapter_spine.set_current_chapter(None)
        except Exception:
            pass
        return

    cur = controller._chapter_index_service.get_current_chapter(  # noqa: SLF001
        controller._chapters,
        current_char_offset=int(current_char_offset),
    )
    controller._current_chapter = cur  # noqa: SLF001
    prev = controller._chapter_index_service.get_previous_chapter(  # noqa: SLF001
        controller._chapters,
        current_char_offset=int(current_char_offset),
    )
    nxt = controller._chapter_index_service.get_next_chapter(  # noqa: SLF001
        controller._chapters,
        current_char_offset=int(current_char_offset),
    )
    try:
        controller.window.set_chapter_controls_enabled(
            previous=prev is not None,
            next_=nxt is not None,
        )
    except Exception:
        pass
    try:
        if hasattr(controller.window, "chapter_spine"):
            controller.window.chapter_spine.set_current_chapter(cur)
    except Exception:
        pass


def previous_chapter(controller) -> None:
    jump_to_chapter(controller, direction="previous")


def next_chapter(controller) -> None:
    jump_to_chapter(controller, direction="next")


def jump_to_chapter(controller, *, direction: str) -> None:
    if not controller._chapters:  # noqa: SLF001
        return

    _chunk, char_offset = controller.narration_service.current_position()
    if char_offset is None:
        return

    if direction == "previous":
        target = controller._chapter_index_service.get_previous_chapter(  # noqa: SLF001
            controller._chapters,
            current_char_offset=int(char_offset),
        )
    else:
        target = controller._chapter_index_service.get_next_chapter(  # noqa: SLF001
            controller._chapters,
            current_char_offset=int(char_offset),
        )
    if target is None:
        return

    voice = controller._selected_voice()  # noqa: SLF001
    if voice is None:
        return

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
