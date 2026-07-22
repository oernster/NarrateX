"""Signal wiring for UiController.

Extracted to keep ui_controller.py within the 400-line module size limit.
"""

from __future__ import annotations


def connect_signals(controller) -> None:
    controller.window.select_book_clicked.connect(controller.select_book)

    # Voice picker toggles (sex + region filter the voice dropdown).
    if hasattr(controller.window, "voice_sex_toggle_clicked"):
        try:
            controller.window.voice_sex_toggle_clicked.connect(
                controller.toggle_voice_sex
            )
        except Exception:
            pass
    if hasattr(controller.window, "voice_region_toggle_clicked"):
        try:
            controller.window.voice_region_toggle_clicked.connect(
                controller.cycle_voice_region
            )
        except Exception:
            pass

    # Reader click-to-seek.
    if hasattr(controller.window, "reader_seek_requested"):
        try:
            from voice_reader.ui._ui_controller_seek import seek_to_char_offset

            controller.window.reader_seek_requested.connect(
                lambda off: seek_to_char_offset(controller, int(off))
            )
        except Exception:
            pass

    # Playback transport:
    # - new UI uses a single play/pause toggle
    # - keep legacy separate play/pause signals for backwards compatibility
    if hasattr(controller.window, "play_pause_clicked"):
        try:
            controller.window.play_pause_clicked.connect(controller.toggle_play_pause)
        except Exception:
            pass
    controller.window.stop_clicked.connect(controller.stop)

    if hasattr(controller.window, "previous_chapter_clicked"):
        try:
            controller.window.previous_chapter_clicked.connect(
                controller.previous_chapter
            )
        except Exception:
            pass
    if hasattr(controller.window, "next_chapter_clicked"):
        try:
            controller.window.next_chapter_clicked.connect(controller.next_chapter)
        except Exception:
            pass
    if hasattr(controller.window, "bookmarks_clicked"):
        try:
            controller.window.bookmarks_clicked.connect(
                controller.open_bookmarks_dialog
            )
        except Exception:
            pass
    if hasattr(controller.window, "ideas_clicked"):
        try:
            controller.window.ideas_clicked.connect(controller.open_sections_dialog)
        except Exception:
            pass
    if hasattr(controller.window, "speed_changed"):
        try:
            controller.window.speed_changed.connect(controller.set_speed)
        except Exception:
            pass
    if hasattr(controller.window, "volume_changed"):
        try:
            controller.window.volume_changed.connect(controller.set_volume)
        except Exception:
            pass
