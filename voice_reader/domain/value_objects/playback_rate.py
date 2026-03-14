"""Playback rate value object.

Playback rate is a *playback* concern only:
- it must not alter synthesis
- it must not alter cache keys
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaybackRate:
    """Validated playback rate multiplier."""

    value: float

    MIN = 0.75
    MAX = 2.00
    DEFAULT = 1.00

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)):
            raise TypeError("PlaybackRate must be numeric")
        v = float(self.value)
        if not self.MIN <= v <= self.MAX:
            raise ValueError("PlaybackRate outside allowed range")

    @property
    def multiplier(self) -> float:
        return float(self.value)

    @classmethod
    def default(cls) -> "PlaybackRate":
        return cls(cls.DEFAULT)
