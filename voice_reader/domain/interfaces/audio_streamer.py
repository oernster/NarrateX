"""Domain interface: audio streamer / player.

The application layer depends on this abstraction for testability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Protocol

OnChunkCallback = Callable[[int], None]


class AudioStreamer(Protocol):
    def start(
        self,
        *,
        chunk_audio_paths: Iterable[Path],
        on_chunk_start: OnChunkCallback | None = None,
        on_chunk_end: OnChunkCallback | None = None,
    ) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...
