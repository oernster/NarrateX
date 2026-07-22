"""Coverage for _ui_controller_wiring.connect_signals exception branches."""

from __future__ import annotations

from types import SimpleNamespace

import voice_reader.ui._ui_controller_wiring as _wiring


class _ExplodingSignal:
    """Signal whose connect() always raises."""

    def connect(self, *_):
        raise RuntimeError("connect exploded")


class _SilentSignal:
    """Signal whose connect() silently succeeds."""

    def connect(self, *_):
        pass


def _make_window(**extras):
    """Return a fake window with mandatory signals working and optional signals exploding."""
    attrs = {
        # Mandatory: NOT in try/except, must not raise.
        "select_book_clicked": _SilentSignal(),
        "stop_clicked": _SilentSignal(),
        # Optional: inside try/except, intentionally raise to cover except branches.
        "remove_book_clicked": _ExplodingSignal(),
        "voice_combo": SimpleNamespace(currentIndexChanged=_ExplodingSignal()),
        "voice_sex_toggle_clicked": _ExplodingSignal(),
        "voice_region_toggle_clicked": _ExplodingSignal(),
        "reader_seek_requested": _ExplodingSignal(),
        "play_pause_clicked": _ExplodingSignal(),
        "previous_chapter_clicked": _ExplodingSignal(),
        "next_chapter_clicked": _ExplodingSignal(),
        "bookmarks_clicked": _ExplodingSignal(),
        "ideas_clicked": _ExplodingSignal(),
        "speed_changed": _ExplodingSignal(),
        "volume_changed": _ExplodingSignal(),
    }
    attrs.update(extras)
    return SimpleNamespace(**attrs)


def _make_controller(window):
    return SimpleNamespace(
        window=window,
        select_book=lambda: None,
        remove_current_book=lambda **_: None,
        toggle_voice_sex=lambda: None,
        cycle_voice_region=lambda: None,
        toggle_play_pause=lambda: None,
        stop=lambda: None,
        previous_chapter=lambda: None,
        next_chapter=lambda: None,
        open_bookmarks_dialog=lambda: None,
        open_sections_dialog=lambda: None,
        set_speed=lambda _: None,
        set_volume=lambda _: None,
    )


def test_connect_signals_swallows_all_connect_exceptions() -> None:
    """All connect() calls raising must not propagate out of connect_signals."""
    controller = _make_controller(_make_window())
    _wiring.connect_signals(controller)  # must not raise


def test_connect_signals_skips_optional_signals_when_absent() -> None:
    """Window with only mandatory signals must not raise."""
    window = SimpleNamespace(
        select_book_clicked=_SilentSignal(),
        stop_clicked=_SilentSignal(),
    )
    controller = _make_controller(window)
    _wiring.connect_signals(controller)  # must not raise
