from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import queue
import threading
import time

from voice_reader.application.services.narration.synthesis_common import (
    SynthesisStream,
    gate_synthesis_window,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration._types import PlaybackCandidate
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.voice_profile import VoiceProfile
    from voice_reader.domain.interfaces.tts_engine import TTSEngine


def start_parallel_kokoro_synthesis(
    service: NarrationService,
    *,
    candidates: list[PlaybackCandidate],
    voice: VoiceProfile,
    book_id: str,
    tts_engine: TTSEngine,
    workers: int,
) -> SynthesisStream:
    path_q: "queue.Queue[Path | None]" = queue.Queue(maxsize=8)
    synth_done = threading.Event()
    synth_errors: list[BaseException] = []

    work_q: "queue.Queue[tuple[int, PlaybackCandidate] | None]" = queue.Queue()
    for i, cand in enumerate(candidates):
        work_q.put((int(i), cand))
    for _ in range(max(1, int(workers))):
        work_q.put(None)

    results: dict[int, Path] = {}
    results_lock = threading.Lock()

    def _worker() -> None:
        try:
            while not service._stop_event.is_set():  # noqa: SLF001
                item = work_q.get()
                if item is None:
                    return
                idx, cand = item

                gate_synthesis_window(service, idx=int(idx))

                if service._stop_event.is_set():  # noqa: SLF001
                    return

                if service._pause_event.is_set():  # noqa: SLF001
                    while (
                        service._pause_event.is_set()  # noqa: SLF001
                        and not service._stop_event.is_set()  # noqa: SLF001
                        and idx > max(service._current_play_index, 0)  # noqa: SLF001
                    ):
                        time.sleep(0.05)

                if service._stop_event.is_set():  # noqa: SLF001
                    return

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

                with results_lock:
                    results[int(idx)] = cand.audio_path
        except BaseException as exc:  # pragma: no cover
            synth_errors.append(exc)

    for i in range(max(1, int(workers))):
        threading.Thread(
            target=_worker,
            name=f"tts-kokoro-{i}",
            daemon=True,
        ).start()

    def _publisher() -> None:
        try:
            next_idx = 0
            while not service._stop_event.is_set() and next_idx < len(
                candidates
            ):  # noqa: SLF001
                with results_lock:
                    path = results.get(int(next_idx))
                if path is None:
                    time.sleep(0.01)
                    continue
                path_q.put(path)
                next_idx += 1
        finally:
            synth_done.set()
            try:
                path_q.put_nowait(None)
            except Exception:
                try:
                    path_q.put(None)
                except Exception:
                    pass

    threading.Thread(
        target=_publisher,
        name="tts-publisher",
        daemon=True,
    ).start()

    return SynthesisStream(
        path_q=path_q, synth_done=synth_done, synth_errors=synth_errors
    )
