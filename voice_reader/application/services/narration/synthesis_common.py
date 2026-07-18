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


def startup_warmup_tts(
    service: NarrationService,
    *,
    voice: VoiceProfile,
    tts_engine: TTSEngine,
) -> None:
    """Synthesise a single word at startup to load the TTS model into memory.

    Emits SYNTHESIZING state so the UI progress bar animates, then resets to
    IDLE when done.  Safe to call from a background daemon thread.
    """
    service._set_state(  # noqa: SLF001
        NarrationState(
            status=NarrationStatus.SYNTHESIZING,
            current_chunk_id=None,
            prefetch_chunk_id=None,
            playback_chunk_id=None,
            total_chunks=None,
            progress=0.0,
            message="Preparing audio...",
        )
    )
    try:
        tmp = (
            service.cache_repo.audio_path(
                book_id="__startup__",
                voice_name=voice.name,
                chunk_id=-999999,
            )
        ).with_name("__startup_warmup.wav")
        service.cache_repo.ensure_parent_dir(tmp)
        tts_engine.synthesize_to_file(
            text=".",
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
        service._log.debug("Startup TTS warmup failed", exc_info=True)  # noqa: SLF001
    finally:
        service._set_state(  # noqa: SLF001
            NarrationState(
                status=NarrationStatus.IDLE,
                current_chunk_id=None,
                prefetch_chunk_id=None,
                playback_chunk_id=None,
                total_chunks=None,
                progress=0.0,
                message="",
            )
        )


def presynthesize_start_chunks(
    service: NarrationService,
    *,
    voice: VoiceProfile,
    tts_engine: TTSEngine,
    cancel_event: threading.Event,
    n_chunks: int = 2,
) -> None:
    """Synthesise and cache the first n_chunks at the playback start position.

    Runs in a background thread after book load so pressing Play is near-instant.
    Emits no state transitions; silently aborts on cancel_event or any error.
    """
    if (
        service._book is None or service.navigation_chunk_service is None
    ):  # noqa: SLF001
        return

    try:
        chunks, _ = service.navigation_chunk_service.build_chunks(
            book_text=service._book.normalized_text,  # noqa: SLF001
            document=service._book.document_model,  # noqa: SLF001
        )
    except Exception:
        return

    # Resolve start index from resume position if available.
    start_idx = 0
    if service.bookmark_service is not None:
        try:
            rp = service.bookmark_service.load_resume_position(
                book_id=service._book.id  # noqa: SLF001
            )
            if rp is not None:
                resume_char = int(getattr(rp, "char_offset", 0))
                for i, c in enumerate(chunks):
                    mapped = service.sanitized_text_mapper.sanitize_with_mapping(
                        original_text=c.text
                    )
                    if not mapped.speak_text:
                        continue
                    if int(c.start_char) <= resume_char < int(c.end_char):
                        start_idx = i
                        break
                    if int(c.start_char) >= resume_char:
                        start_idx = i
                        break
        except Exception:
            pass

    try:
        from voice_reader.application.services.narration.cache_key import (
            compute_book_cache_id,
        )

        book_id = compute_book_cache_id(service)
    except Exception:
        return

    synthesized = 0
    for chunk in list(chunks)[start_idx:]:
        if cancel_event.is_set() or service._stop_event.is_set():  # noqa: SLF001
            return
        if synthesized >= n_chunks:
            break
        try:
            mapped = service.sanitized_text_mapper.sanitize_with_mapping(
                original_text=chunk.text
            )
        except Exception:
            continue
        speak_text = mapped.speak_text
        if not speak_text:
            continue
        audio_path = service.cache_repo.audio_path(
            book_id=book_id,
            voice_name=voice.name,
            chunk_id=chunk.chunk_id,
        )
        if not service.cache_repo.exists(
            book_id=book_id,
            voice_name=voice.name,
            chunk_id=chunk.chunk_id,
        ):
            try:
                service.cache_repo.ensure_parent_dir(audio_path)
                tts_engine.synthesize_to_file(
                    text=speak_text,
                    voice_profile=voice,
                    output_path=audio_path,
                    device=service.device,
                    language=service.language,
                )
            except Exception:
                service._log.debug(  # noqa: SLF001
                    "Pre-synthesis failed for chunk %s", chunk.chunk_id
                )
                return
        synthesized += 1


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
