"""Playback volume value object.

Volume is a *playback* concern only:
- it must not alter synthesis
- it must not alter cache keys

Unlike playback rate, volume is intentionally forgiving: values are clamped
into the valid range so UI sliders and external callers can pass raw numbers
without raising.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaybackVolume:
    """Normalized playback volume multiplier."""

    value: float

    MIN = 0.0
    MAX = 1.0
    DEFAULT = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)):
            raise TypeError("PlaybackVolume must be numeric")
        v = float(self.value)
        v = max(self.MIN, min(self.MAX, v))
        object.__setattr__(self, "value", v)

    @property
    def multiplier(self) -> float:
        return float(self.value)

    @classmethod
    def default(cls) -> "PlaybackVolume":
        return cls(cls.DEFAULT)
