from __future__ import annotations

from typing import TYPE_CHECKING
import time

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration.alignment import resolve_audible_span

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration._types import PlaybackCandidate
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.application.services.narration.synthesis_common import (
        SynthesisStream,
    )
    from voice_reader.domain.entities.voice_profile import VoiceProfile


def play(
    service: NarrationService,
    *,
    candidates: list[PlaybackCandidate],
    stream: SynthesisStream,
    voice: VoiceProfile,
    book_id: str,
) -> None:
    playback_total = len(candidates)
    playback_chunks = [c.chunk for c in candidates]
    playback_text_maps = [(c.speak_text, c.speak_to_original) for c in candidates]

    def audio_paths_iter():
        while not service._stop_event.is_set():  # noqa: SLF001
            item = stream.path_q.get()
            if item is None:
                return
            yield item

    def on_start(play_index: int) -> None:
        # Mark that we have actually begun audible playback. This is used by
        # exit-time persistence to avoid creating resume JSON for books the user
        # never listened to.
        try:
            service._played_any_chunk = True  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass
        service._current_play_index = int(play_index)  # noqa: SLF001
        if play_index < 0 or play_index >= playback_total:
            return
        c = playback_chunks[int(play_index)]
        try:
            on_progress._last_emit_ms = -1  # type: ignore[attr-defined]
        except Exception:
            pass
        service._set_state(
            NarrationState(
                status=NarrationStatus.PLAYING,
                current_chunk_id=int(play_index),
                playback_chunk_id=int(play_index),
                prefetch_chunk_id=service.state.prefetch_chunk_id,
                total_chunks=int(playback_total),
                progress=int(play_index) / max(int(playback_total), 1),
                message=f"Playing chunk {int(play_index) + 1}/{int(playback_total)}",
                audible_start=c.start_char,
                audible_end=c.end_char,
                highlight_start=c.start_char,
                highlight_end=c.end_char,
            )
        )

    def on_end(play_index: int) -> None:
        try:
            if not service._stop_after_current_chunk.is_set():  # noqa: SLF001
                return
        except Exception:  # pragma: no cover
            return

        try:
            service._stop_after_current_chunk.clear()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass
        service._stop_event.set()  # noqa: SLF001
        try:
            service.audio_streamer.stop()
        except Exception:  # pragma: no cover
            pass

    def on_progress(play_index: int, chunk_local_ms: int) -> None:
        if play_index < 0 or play_index >= playback_total:
            return
        c = playback_chunks[int(play_index)]

        try:
            last = int(
                getattr(on_progress, "_last_emit_ms", -1)  # type: ignore[attr-defined]
            )
        except Exception:
            last = -1
        ms = int(max(0, chunk_local_ms))
        if last >= 0 and (ms - last) < 25:
            return
        try:
            on_progress._last_emit_ms = ms  # type: ignore[attr-defined]
        except Exception:
            pass

        if (
            service._pause_event.is_set() or service._stop_event.is_set()
        ):  # noqa: SLF001
            return

        a_start, a_end = resolve_audible_span(
            service,
            chunk=c,
            play_index=int(play_index),
            chunk_local_ms=int(ms),
            playback_text_maps=playback_text_maps,
            book_id=book_id,
            voice=voice,
        )

        if a_start is None or a_end is None:
            a_start, a_end = int(c.start_char), int(c.end_char)

        st = service.state
        if (
            st.playback_chunk_id == int(play_index)
            and st.audible_start == a_start
            and st.audible_end == a_end
        ):
            return

        service._set_state(
            NarrationState(
                status=st.status,
                current_chunk_id=int(play_index),
                playback_chunk_id=int(play_index),
                prefetch_chunk_id=st.prefetch_chunk_id,
                total_chunks=st.total_chunks,
                progress=st.progress,
                message=st.message,
                audible_start=a_start,
                audible_end=a_end,
                highlight_start=st.highlight_start,
                highlight_end=st.highlight_end,
            )
        )

    # Slight delay to allow synthesis prefetch to start.
    # (No-op for most streamers; mainly to keep deterministic tests stable.)
    time.sleep(0)

    service.audio_streamer.start(
        chunk_audio_paths=audio_paths_iter(),
        on_chunk_start=on_start,
        on_chunk_end=on_end,
        on_playback_progress=on_progress,
    )
