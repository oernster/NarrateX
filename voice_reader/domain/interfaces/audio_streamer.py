"""Domain interface: audio streamer / player.

The application layer depends on this abstraction for testability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Protocol

from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

OnChunkCallback = Callable[[int], None]
OnPlaybackProgressCallback = Callable[[int, int], None]


class AudioStreamer(Protocol):
    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start: OnChunkCallback | None = None,
        on_chunk_end: OnChunkCallback | None = None,
        on_playback_progress: OnPlaybackProgressCallback | None = None,
    ) -> None: ...

    def set_playback_rate(self, rate: PlaybackRate) -> None: ...

    def set_volume(self, volume: PlaybackVolume) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...
