from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.navigation_chunk_service import (
    NavigationChunkService,
)
from voice_reader.domain.services.reading_start_service import ReadingStartService
from voice_reader.domain.value_objects.playback_rate import PlaybackRate
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def init_runtime_state(service: NarrationService) -> None:
    service._log = logging.getLogger(service.__class__.__name__)  # noqa: SLF001
    service._listeners = []  # noqa: SLF001
    service._stop_event = threading.Event()  # noqa: SLF001
    service._stop_after_current_chunk = threading.Event()  # noqa: SLF001
    service._play_thread = None  # noqa: SLF001
    service._lock = threading.Lock()  # noqa: SLF001
    service._state = NarrationState(
        status=NarrationStatus.IDLE,
        current_chunk_id=None,
        playback_chunk_id=None,
        prefetch_chunk_id=None,
        total_chunks=None,
        progress=0.0,
    )
    service._book = None  # noqa: SLF001
    service._chunks = []  # noqa: SLF001
    service._voice = None  # noqa: SLF001
    service._start_char = None  # noqa: SLF001
    service._cache_book_id = None  # noqa: SLF001
    service._pause_event = threading.Event()  # noqa: SLF001
    service._current_play_index = -1  # noqa: SLF001
    service._start_playback_index = 0  # noqa: SLF001
    # True once audio playback has actually started at least one chunk.
    # Used to avoid creating resume JSON for books the user never listened to.
    service._played_any_chunk = False  # noqa: SLF001
    service._playback_rate = PlaybackRate.default()  # noqa: SLF001
    service._volume = PlaybackVolume.default()  # noqa: SLF001
    service._persist_resume = True  # noqa: SLF001

    # Restore persisted volume (best-effort).
    if service.preferences_repo is not None:
        try:
            restored = service.preferences_repo.load_playback_volume()
        except Exception:
            restored = None
        if restored is not None:
            service._volume = restored  # noqa: SLF001

    if service.navigation_chunk_service is None:
        service.navigation_chunk_service = NavigationChunkService(
            reading_start_detector=service.reading_start_detector,
            chunking_service=service.chunking_service,
        )

    # Ensure the playback layer is initialized with our defaults.
    try:
        service.audio_streamer.set_playback_rate(service._playback_rate)  # noqa: SLF001
    except Exception:
        pass
    try:
        service.audio_streamer.set_volume(service._volume)  # noqa: SLF001
    except Exception:
        pass


def default_reading_start_detector():
    # keep creation local to avoid mutable default objects in the dataclass signature
    return ReadingStartService()
