from __future__ import annotations

from typing import TYPE_CHECKING

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration.persistence import (
    maybe_save_resume_position,
)

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService


def request_stop_after_current_chunk(service: NarrationService) -> None:
    try:
        service._stop_after_current_chunk.set()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass


def wait(service: NarrationService, timeout_seconds: float | None = None) -> bool:
    t = service._play_thread  # noqa: SLF001
    if t is None:
        return True
    t.join(timeout=timeout_seconds)
    return not t.is_alive()


def start(service: NarrationService) -> None:
    with service._lock:  # noqa: SLF001
        try:
            service._stop_after_current_chunk.clear()  # noqa: SLF001
        except Exception:  # pragma: no cover
            pass

        if service._play_thread and service._play_thread.is_alive():  # noqa: SLF001
            return
        if service._book is None or service._voice is None:  # noqa: SLF001
            raise ValueError("Book and voice must be set before start")
        if not service._chunks:  # noqa: SLF001
            service._chunks = service.chunking_service.chunk_text(  # noqa: SLF001
                service._book.normalized_text  # noqa: SLF001
            )

        service._stop_event.clear()  # noqa: SLF001
        import threading

        service._play_thread = threading.Thread(  # noqa: SLF001
            target=service._run,
            name="narration-thread",
            daemon=True,
        )
        service._play_thread.start()  # noqa: SLF001


def pause(service: NarrationService) -> None:
    service._pause_event.set()  # noqa: SLF001
    service.audio_streamer.pause()

    paused_chunk_id = (
        service._current_play_index  # noqa: SLF001
        if service._current_play_index is not None
        and service._current_play_index >= 0  # noqa: SLF001
        else service.state.current_chunk_id
    )
    st = service.state
    service._set_state(
        NarrationState(
            status=NarrationStatus.PAUSED,
            current_chunk_id=paused_chunk_id,
            playback_chunk_id=paused_chunk_id,
            prefetch_chunk_id=st.prefetch_chunk_id,
            total_chunks=st.total_chunks,
            progress=st.progress,
            message="Paused",
            audible_start=st.audible_start,
            audible_end=st.audible_end,
            highlight_start=st.highlight_start,
            highlight_end=st.highlight_end,
        )
    )

    maybe_save_resume_position(service)


def resume(service: NarrationService) -> None:
    service._pause_event.clear()  # noqa: SLF001
    service.audio_streamer.resume()
    st = service.state
    service._set_state(
        NarrationState(
            status=NarrationStatus.PLAYING,
            current_chunk_id=st.current_chunk_id,
            playback_chunk_id=st.current_chunk_id,
            prefetch_chunk_id=st.prefetch_chunk_id,
            total_chunks=st.total_chunks,
            progress=st.progress,
            message="Playing",
            audible_start=st.audible_start,
            audible_end=st.audible_end,
            highlight_start=st.highlight_start,
            highlight_end=st.highlight_end,
        )
    )


def stop(service: NarrationService, *, persist_resume: bool = True) -> None:
    if bool(persist_resume):
        maybe_save_resume_position(service)

    service._stop_event.set()  # noqa: SLF001
    try:
        service._stop_after_current_chunk.clear()  # noqa: SLF001
    except Exception:  # pragma: no cover
        pass
    service._pause_event.clear()  # noqa: SLF001
    service.audio_streamer.stop()

    wait(service, timeout_seconds=2.0)

    service._set_state(
        NarrationState(
            status=NarrationStatus.STOPPED,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=service.state.total_chunks,
            progress=0.0,
            message="Stopped",
            audible_start=None,
            audible_end=None,
            highlight_start=None,
            highlight_end=None,
        )
    )
    service._persist_resume = True  # noqa: SLF001


def on_app_exit(service: NarrationService) -> None:
    maybe_save_resume_position(service)
