"""Audio resampling utilities.

This is used purely for playback-rate adjustment. It must not alter cache or TTS.
"""

from __future__ import annotations

import numpy as np


class AudioResampler:
    """Resample float32 audio arrays by linear interpolation.

    Notes:
    - This changes the number of samples, thus changing playback speed.
    - Pitch will also change (simple resampling), which is acceptable for this
      iteration given the constraint to operate in playback layer only.
    """

    def resample_for_rate(self, audio: np.ndarray, rate: float) -> np.ndarray:
        if rate == 1.0 or audio.size == 0:
            return audio

        if audio.ndim == 1:
            return self._resample_mono(audio, rate)

        channels = [
            self._resample_mono(audio[:, i], rate) for i in range(audio.shape[1])
        ]
        min_len = min(len(c) for c in channels)
        channels = [c[:min_len] for c in channels]
        return np.stack(channels, axis=1)

    def _resample_mono(self, audio: np.ndarray, rate: float) -> np.ndarray:
        old_len = len(audio)
        new_len = max(1, int(round(old_len / float(rate))))

        old_pos = np.arange(old_len, dtype=np.float32)
        new_pos = np.linspace(0, old_len - 1, num=new_len, dtype=np.float32)

        return np.interp(new_pos, old_pos, audio).astype(np.float32)
