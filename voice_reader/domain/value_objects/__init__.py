"""Domain value objects.

Value objects are small, immutable types that:
- validate invariants at the boundary
- avoid passing raw primitives (e.g., floats) through the domain/application
"""

from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

__all__ = [
    "PlaybackRate",
    "PlaybackVolume",
]
