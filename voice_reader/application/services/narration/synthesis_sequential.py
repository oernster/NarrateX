from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import queue
import threading

from voice_reader.application.services.narration.synthesis_common import (
    SynthesisStream,
    gate_synthesis_window,
    maybe_warmup_tts,
    put_or_stop,
    set_synth_state,
    signal_end_of_stream,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration._types import PlaybackCandidate
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.voice_profile import VoiceProfile
    from voice_reader.domain.interfaces.tts_engine import TTSEngine


def start_sequential_synthesis(
    service: NarrationService,
    *,
    candidates: list[PlaybackCandidate],
    voice: VoiceProfile,
    book_id: str,
    tts_engine: TTSEngine,
) -> SynthesisStream:
    path_q: "queue.Queue[Path | None]" = queue.Queue(maxsize=8)
    synth_done = threading.Event()
    synth_errors: list[BaseException] = []

    total = len(candidates)

    def _worker() -> None:
        try:
            maybe_warmup_tts(
                service, voice=voice, book_id=book_id, tts_engine=tts_engine
            )
            for idx, cand in enumerate(candidates):
                if service._stop_event.is_set():  # noqa: SLF001
                    return

                gate_synthesis_window(service, idx=int(idx))
                if service._stop_event.is_set():  # noqa: SLF001
                    return

                set_synth_state(service, idx=int(idx), total=int(total))

                if not service.cache_repo.exists(
                    book_id=book_id,
                    voice_name=voice.name,
                    chunk_id=cand.chunk.chunk_id,
                ):
                    service.cache_repo.ensure_parent_dir(cand.audio_path)
                    tts_engine.synthesize_to_file(
                        text=cand.speak_text,
                        voice_profile=voice,
                        output_path=cand.audio_path,
                        device=service.device,
                        language=service.language,
                    )
                if not put_or_stop(
                    path_q,
                    cand.audio_path,
                    stop_event=service._stop_event,  # noqa: SLF001
                ):
                    return
        except BaseException as exc:  # pragma: no cover
            synth_errors.append(exc)
            service._log.exception("Synthesis worker failed")  # noqa: SLF001
        finally:
            synth_done.set()
            signal_end_of_stream(
                path_q,
                stop_event=service._stop_event,  # noqa: SLF001
            )

    threading.Thread(
        target=_worker,
        name="tts-synth",
        daemon=True,
    ).start()

    return SynthesisStream(
        path_q=path_q, synth_done=synth_done, synth_errors=synth_errors
    )
