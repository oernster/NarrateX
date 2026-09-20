"""The transport's entry points on the controller, as one capability.

Play, pause, stop, the toggle the one button drives and the two settings beside
it. Each is a name a signal connects to, so each has to be a method; the
behaviour is in `_ui_controller_playback.py` and stays there.
"""

from __future__ import annotations

from voice_reader.ui._ui_controller_playback import (
    pause,
    play,
    set_speed,
    set_volume,
    stop,
    toggle_play_pause,
)


class TransportApi:
    """What the transport row asks the controller to do."""

    def set_speed(self, text: str) -> None:
        return set_speed(self, text)

    def set_volume(self, value: int) -> None:
        return set_volume(self, value)

    def play(self) -> None:
        return play(self)

    def pause(self) -> None:
        return pause(self)

    def stop(self) -> None:
        return stop(self)

    def toggle_play_pause(self) -> None:
        return toggle_play_pause(self)
