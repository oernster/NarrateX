from __future__ import annotations

from typing import TYPE_CHECKING
import time

import os

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration.audio_playback import play
from voice_reader.application.services.narration.candidates import (
    build_playback_candidates,
)
from voice_reader.application.services.narration.synthesis_parallel_kokoro import (
    start_parallel_kokoro_synthesis,
)
from voice_reader.application.services.narration.synthesis_sequential import (
    start_sequential_synthesis,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def run(service: NarrationService) -> None:
    assert service._book is not None  # noqa: SLF001
    assert service._voice is not None  # noqa: SLF001

    voice = service._voice  # noqa: SLF001
    tts_engine = service.tts_engine
    book_id = service.book_id()

    try:
        candidates = build_playback_candidates(service, voice=voice, book_id=book_id)

        start_idx = max(
            0, min(int(service._start_playback_index), len(candidates))
        )  # noqa: SLF001
        if start_idx:
            candidates = candidates[start_idx:]

        playback_total = len(candidates)

        # Optional Kokoro-only parallel synthesis.
        try:
            kokoro_workers = int(os.getenv("NARRATEX_KOKORO_WORKERS", "0"))
        except Exception:
            kokoro_workers = 0

        is_kokoro_native = False
        try:
            if voice.reference_audio_paths:
                is_kokoro_native = False
            elif tts_engine.engine_name.strip().lower() == "kokoro":
                is_kokoro_native = True
            else:
                native = getattr(tts_engine, "native_engine", None)
                if (
                    native is not None
                    and getattr(native, "engine_name", "").strip().lower() == "kokoro"
                ):
                    is_kokoro_native = True
        except Exception:
            is_kokoro_native = False

        if is_kokoro_native and kokoro_workers and kokoro_workers > 1:
            stream = start_parallel_kokoro_synthesis(
                service,
                candidates=candidates,
                voice=voice,
                book_id=book_id,
                tts_engine=tts_engine,
                workers=int(kokoro_workers),
            )
        else:
            stream = start_sequential_synthesis(
                service,
                candidates=candidates,
                voice=voice,
                book_id=book_id,
                tts_engine=tts_engine,
            )

        # Optional prefetch: wait for a couple paths to be ready so playback
        # doesn't pause between early chunks.
        try:
            prefetch = int(os.getenv("NARRATEX_PREFETCH_CHUNKS", "2"))
        except Exception:
            prefetch = 2
        if prefetch > 0:
            t0_prefetch = time.perf_counter()
            while (
                not stream.synth_done.is_set()
                and stream.path_q.qsize() < int(prefetch)
                and not service._stop_event.is_set()  # noqa: SLF001
                and (time.perf_counter() - t0_prefetch) < 30.0
            ):
                time.sleep(0.05)

        play(
            service,
            candidates=candidates,
            stream=stream,
            voice=voice,
            book_id=book_id,
        )

        if stream.synth_errors:
            raise stream.synth_errors[0]

        if service._stop_event.is_set():  # noqa: SLF001
            service._set_state(
                NarrationState(
                    status=NarrationStatus.STOPPED,
                    current_chunk_id=None,
                    playback_chunk_id=None,
                    prefetch_chunk_id=None,
                    total_chunks=int(playback_total),
                    progress=0.0,
                    message="Stopped",
                    audible_start=None,
                    audible_end=None,
                    highlight_start=None,
                    highlight_end=None,
                )
            )
            return

        service._set_state(
            NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                playback_chunk_id=None,
                prefetch_chunk_id=service.state.prefetch_chunk_id,
                total_chunks=int(playback_total),
                progress=1.0,
                message="Done",
            )
        )
    except Exception as exc:  # pragma: no cover
        # Hardening: if a synthesis/playback failure occurs mid-book (e.g. TTS
        # produced no audio for a separator-only chunk), persist a best-effort
        # resume position so the next Play doesn't restart at the beginning.
        try:
            service._maybe_save_resume_position()  # noqa: SLF001
        except Exception:
            pass

        service._log.exception("Narration failed")  # noqa: SLF001
        service._set_state(
            NarrationState(
                status=NarrationStatus.ERROR,
                current_chunk_id=service.state.current_chunk_id,
                playback_chunk_id=service.state.playback_chunk_id,
                prefetch_chunk_id=service.state.prefetch_chunk_id,
                total_chunks=service.state.total_chunks,
                progress=service.state.progress,
                message=str(exc),
            )
        )
