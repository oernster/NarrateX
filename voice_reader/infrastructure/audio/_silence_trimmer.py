"""Silence trimming used by the audio streamer.

Kept separate so the main streamer implementation stays compact.
"""

from __future__ import annotations


def trim_silence(
    data,
    *,
    sample_rate: int,
    threshold: float,
    pad_ms: int,
    trim_leading: bool,
    trim_trailing: bool,
):
    """Trim leading/trailing near-silence from an audio array.

    This reduces perceived gaps between chunk WAVs and removes the common
    "fade out / fade in" sensation that is actually leading/trailing silence.
    """

    try:
        import numpy as np

        if not isinstance(data, np.ndarray):
            return data
        if data.size == 0:
            return data

        # Reduce to mono for detection.
        if data.ndim == 2:
            mono = np.mean(data.astype(np.float32), axis=1)
        else:
            mono = data.astype(np.float32)

        abs_m = np.abs(mono)
        idx = np.where(abs_m > float(threshold))[0]
        if idx.size == 0:
            # All silence (or threshold too high) — keep unchanged.
            return data

        pad = int(max(0, sample_rate) * (pad_ms / 1000.0))
        start = 0
        end = int(mono.shape[0])
        if trim_leading:
            start = max(int(idx[0]) - pad, 0)
        if trim_trailing:
            end = min(int(idx[-1]) + pad, int(mono.shape[0]))
        if end <= start:
            return data
        return data[start:end]
    except Exception:
        return data
