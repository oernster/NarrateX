"""Backwards-compatible module wrapper.

Historically the playback implementation lived at
`voice_reader.infrastructure.audio.audio_streamer`.

To keep files small and focused (≤400 LOC), the implementation is now in
`voice_reader.infrastructure.audio.sounddevice_streamer`.
"""

from __future__ import annotations

from voice_reader.infrastructure.audio._silence_trimmer import (
    trim_silence as _trim_silence,
)
from voice_reader.infrastructure.audio._sounddevice_helpers import (
    safe_output_device as _safe_output_device,
)
from voice_reader.infrastructure.audio._sounddevice_helpers import (
    sd_play as _sd_play,
)
from voice_reader.infrastructure.audio.sounddevice_streamer import (
    SoundDeviceAudioStreamer,
)

__all__ = [
    "SoundDeviceAudioStreamer",
    "_trim_silence",
    "_safe_output_device",
    "_sd_play",
]
