from __future__ import annotations

import pytest

from voice_reader.domain.value_objects.playback_rate import PlaybackRate


def test_default_is_one() -> None:
    assert PlaybackRate.default().multiplier == 1.0


@pytest.mark.parametrize("v", [0.75, 1.25, 2.0])
def test_accepts_valid_range(v: float) -> None:
    assert PlaybackRate(v).multiplier == float(v)


@pytest.mark.parametrize("v", [0.74, 2.01])
def test_rejects_outside_bounds(v: float) -> None:
    with pytest.raises(ValueError):
        PlaybackRate(v)


@pytest.mark.parametrize("v", ["1.0", None, object()])
def test_rejects_non_numeric(v) -> None:
    with pytest.raises(TypeError):
        PlaybackRate(v)  # type: ignore[arg-type]
