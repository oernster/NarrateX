"""Volume scaling helpers (playback-layer concern only)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class VolumeScaler:
    """Scale float32 audio frames by a normalized volume multiplier."""

    def scale(self, frames: np.ndarray, *, volume: float) -> np.ndarray:
        """Return scaled audio frames.

        Assumptions:
        - frames are float32 (or castable to float32)
        - volume is normalized (0.0..1.0). We clamp defensively.

        Notes:
        - We do not apply DSP/normalization, only scalar amplitude changes.
        - We preserve float audio format and avoid additional clipping logic;
          for normalized inputs in [-1, 1], volume<=1.0 cannot introduce new
          clipping.
        """

        v = float(volume)
        if v <= 0.0:
            return np.zeros_like(frames, dtype=np.float32)
        if v >= 1.0:
            # Ensure float32.
            return np.asarray(frames, dtype=np.float32)
        arr = np.asarray(frames, dtype=np.float32)
        return arr * np.float32(v)
