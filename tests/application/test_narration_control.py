"""Transport control: start, pause, resume, stop and the stop-after-chunk flag.

`start` really does spawn a thread, so the stand-in service supplies a trivial
`_run` that sets an event. Nothing here reaches an audio device.
"""

from __future__ import annotations

import pytest

from tests.application.narration_fakes import (
    FakeBook,
    FakeChunkingService,
    FakeNarrationService,
    make_chunks,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration import control


def _ready_service(**kwargs) -> FakeNarrationService:
    service = FakeNarrationService(
        _book=FakeBook(normalized_text="Some prose here."),
        _voice=object(),
        **kwargs,
    )
    return service


class TestStopAfterCurrentChunk:
    def test_the_flag_is_raised(self) -> None:
        service = FakeNarrationService()

        control.request_stop_after_current_chunk(service)

        assert service._stop_after_current_chunk.is_set()


class TestWait:
    def test_waiting_with_no_thread_returns_immediately(self) -> None:
        assert control.wait(FakeNarrationService()) is True

    def test_waiting_for_a_finished_thread_reports_it_finished(self) -> None:
        service = _ready_service(_chunks=make_chunks("one "))
        control.start(service)

        assert control.wait(service, timeout_seconds=5.0) is True
        assert service.ran.is_set()


class TestStart:
    def test_a_started_service_runs_its_playback_target(self) -> None:
        service = _ready_service(_chunks=make_chunks("one "))

        control.start(service)
        service._play_thread.join(timeout=5.0)

        assert service.ran.is_set()
        assert not service._stop_event.is_set()

    def test_starting_twice_does_not_spawn_a_second_thread(self) -> None:
        service = _ready_service(_chunks=make_chunks("one "))
        started = threading_event_thread(service)

        control.start(service)

        assert service._play_thread is started

        # Let the stand-in thread finish rather than leaving it parked.
        service.ran.set()
        started.join(timeout=5.0)
        assert not started.is_alive()

    def test_a_service_with_no_book_refuses_to_start(self) -> None:
        service = FakeNarrationService(_voice=object())

        with pytest.raises(ValueError, match="Book and voice"):
            control.start(service)

    def test_a_service_with_no_voice_refuses_to_start(self) -> None:
        service = FakeNarrationService(_book=FakeBook(normalized_text="text"))

        with pytest.raises(ValueError, match="Book and voice"):
            control.start(service)

    def test_an_unchunked_book_is_chunked_on_the_way_in(self) -> None:
        chunks = make_chunks("one ", "two ")
        service = _ready_service(chunking_service=FakeChunkingService(chunks))

        control.start(service)
        service._play_thread.join(timeout=5.0)

        assert service._chunks == chunks
        assert service.chunking_service.calls == ["Some prose here."]


class TestPauseAndResume:
    def test_pausing_holds_the_position_and_saves_it(self) -> None:
        service = _ready_service(
            _chunks=make_chunks("one "),
            _current_play_index=3,
            state=make_state(playback_chunk_id=3, audible_start=10, total_chunks=5),
        )

        control.pause(service)

        assert service._pause_event.is_set()
        assert "pause" in service.audio_streamer.events
        assert service.state.status is NarrationStatus.PAUSED
        assert service.state.playback_chunk_id == 3
        assert service.bookmark_service.saved

    def test_pausing_before_any_chunk_falls_back_to_the_state_chunk(self) -> None:
        service = _ready_service(state=make_state(current_chunk_id=2))

        control.pause(service)

        assert service.state.playback_chunk_id == 2

    def test_resuming_restores_playing_status(self) -> None:
        service = _ready_service(
            state=make_state(
                status=NarrationStatus.PAUSED,
                current_chunk_id=4,
                audible_start=99,
                total_chunks=5,
            )
        )
        service._pause_event.set()

        control.resume(service)

        assert not service._pause_event.is_set()
        assert "resume" in service.audio_streamer.events
        assert service.state.status is NarrationStatus.PLAYING
        assert service.state.playback_chunk_id == 4
        assert service.state.audible_start == 99


class TestStop:
    def test_stopping_clears_the_position_and_saves_it_first(self) -> None:
        service = _ready_service(state=make_state(playback_chunk_id=1, audible_start=5))

        control.stop(service)

        assert service._stop_event.is_set()
        assert "stop" in service.audio_streamer.events
        assert service.state.status is NarrationStatus.STOPPED
        assert service.state.playback_chunk_id is None
        assert service._persist_resume is True
        assert service.bookmark_service.saved

    def test_stopping_without_persisting_saves_nothing(self) -> None:
        service = _ready_service(state=make_state(playback_chunk_id=1, audible_start=5))

        control.stop(service, persist_resume=False)

        assert service.bookmark_service.saved == []


class TestOnAppExit:
    def test_exiting_saves_the_resume_position(self) -> None:
        service = _ready_service(
            _chunks=make_chunks("one "),
            state=make_state(playback_chunk_id=0, audible_start=0),
        )

        control.on_app_exit(service)

        assert service.bookmark_service.saved


def threading_event_thread(service: FakeNarrationService):
    """Start playback once and return the live thread, for the re-entry test."""

    import threading

    thread = threading.Thread(target=service.ran.wait, daemon=True)
    thread.start()
    service._play_thread = thread
    return thread
