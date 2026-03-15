from __future__ import annotations

import pytest

from voice_reader.domain.value_objects.playback_volume import PlaybackVolume


def test_default_is_one() -> None:
    assert PlaybackVolume.default().multiplier == 1.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (-1.0, 0.0),
        (-0.01, 0.0),
        (0.0, 0.0),
        (0.25, 0.25),
        (1.0, 1.0),
        (1.01, 1.0),
        (10.0, 1.0),
    ],
)
def test_clamps_to_range(raw: float, expected: float) -> None:
    assert PlaybackVolume(raw).multiplier == expected


@pytest.mark.parametrize("raw", ["1.0", None, object()])
def test_rejects_non_numeric(raw) -> None:
    with pytest.raises(TypeError):
        PlaybackVolume(raw)  # type: ignore[arg-type]
