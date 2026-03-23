from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
import queue
import threading
import time

import os

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.voice_profile import VoiceProfile
    from voice_reader.domain.interfaces.tts_engine import TTSEngine


@dataclass(slots=True)
class SynthesisStream:
    path_q: "queue.Queue[Path | None]"
    synth_done: threading.Event
    synth_errors: list[BaseException]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)


def _warmup_enabled() -> bool:
    return os.getenv("NARRATEX_WARMUP", "").strip().lower() in {"1", "true", "yes"}


def maybe_warmup_tts(
    service: NarrationService,
    *,
    voice: VoiceProfile,
    book_id: str,
    tts_engine: TTSEngine,
) -> None:
    if not _warmup_enabled():
        return

    try:
        tmp = (
            service.cache_repo.audio_path(
                book_id=book_id,
                voice_name=voice.name,
                chunk_id=-999999,
            )
        ).with_name("__warmup.wav")
        service.cache_repo.ensure_parent_dir(tmp)
        tts_engine.synthesize_to_file(
            text="Warmup.",
            voice_profile=voice,
            output_path=tmp,
            device=service.device,
            language=service.language,
        )
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception:
        service._log.exception("Warmup synthesis failed")  # noqa: SLF001


def gate_synthesis_window(
    service: NarrationService,
    *,
    idx: int,
) -> None:
    """Block until synthesis for `idx` is within the allowed ahead window."""

    max_ahead = _env_int("NARRATEX_MAX_AHEAD_CHUNKS", 6)
    allowed_ahead = (
        0 if service._pause_event.is_set() else max(0, max_ahead)
    )  # noqa: SLF001

    while not service._stop_event.is_set():  # noqa: SLF001
        base_play = service._current_play_index  # noqa: SLF001
        if base_play < 0:
            # If playback hasn't started yet, allow a small initial window.
            base_play = allowed_ahead
        if idx <= (int(base_play) + allowed_ahead):
            return
        time.sleep(0.05)


def set_synth_state(
    service: NarrationService,
    *,
    idx: int,
    total: int,
) -> None:
    # Preserve the last known audible/highlight spans while synthesizing.
    # Prefetch can race playback, and the UI should not lose the current playhead.
    st = service.state
    service._set_state(
        NarrationState(
            status=NarrationStatus.SYNTHESIZING,
            current_chunk_id=st.current_chunk_id,
            prefetch_chunk_id=int(idx),
            playback_chunk_id=st.playback_chunk_id,
            total_chunks=int(total),
            progress=int(idx) / max(int(total), 1),
            message=f"Preparing chunk {int(idx) + 1}/{int(total)}",
            audible_start=st.audible_start,
            audible_end=st.audible_end,
            highlight_start=st.highlight_start,
            highlight_end=st.highlight_end,
        )
    )
