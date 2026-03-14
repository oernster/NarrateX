from __future__ import annotations

import numpy as np

from voice_reader.infrastructure.audio.resampler import AudioResampler


def test_rate_one_is_unchanged() -> None:
    r = AudioResampler()
    x = np.arange(100, dtype=np.float32)
    out = r.resample_for_rate(x, 1.0)
    assert out is x


def test_rate_gt_one_shortens() -> None:
    r = AudioResampler()
    x = np.arange(100, dtype=np.float32)
    out = r.resample_for_rate(x, 2.0)
    assert out.shape == (50,)


def test_rate_lt_one_lengthens() -> None:
    r = AudioResampler()
    x = np.arange(100, dtype=np.float32)
    out = r.resample_for_rate(x, 0.75)
    assert out.shape[0] > x.shape[0]


def test_empty_input_passthrough() -> None:
    r = AudioResampler()
    x = np.array([], dtype=np.float32)
    out = r.resample_for_rate(x, 1.5)
    assert out is x


def test_stereo_supported() -> None:
    r = AudioResampler()
    x = np.zeros((100, 2), dtype=np.float32)
    out = r.resample_for_rate(x, 1.25)
    assert out.ndim == 2
    assert out.shape[1] == 2
    assert out.shape[0] != 100
