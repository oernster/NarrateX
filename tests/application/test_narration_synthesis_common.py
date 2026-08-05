"""Shared synthesis machinery: warmups, the ahead-window gate and pre-synthesis.

The TTS engine is a hand-written stand-in, so nothing here loads a model or
opens a device. What is being tested is the orchestration around the engine:
when it is called, when it is skipped and what happens when it fails.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

from tests.application.narration_fakes import (
    Boom,
    FakeBook,
    FakeCacheRepo,
    FakeEngine,
    FakeNarrationService,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration.synthesis_common import (
    _env_int,
    gate_synthesis_window,
    maybe_warmup_tts,
    put_or_stop,
    set_synth_state,
    signal_end_of_stream,
    startup_warmup_tts,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.voice_profile import VoiceProfile

VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
TEXT = "Chapter 1\n\nSome prose here.\n"


def _book() -> FakeBook:
    return FakeBook(
        normalized_text=TEXT, document_model=plain_text.build_document(source=TEXT)
    )


class TestEnvironmentInteger:
    def test_an_unset_variable_gives_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NARRATEX_TEST_INT", raising=False)

        assert _env_int("NARRATEX_TEST_INT", 7) == 7

    def test_a_numeric_variable_is_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRATEX_TEST_INT", "3")

        assert _env_int("NARRATEX_TEST_INT", 7) == 3

    def test_a_nonsense_variable_falls_back_to_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARRATEX_TEST_INT", "not a number")

        assert _env_int("NARRATEX_TEST_INT", 7) == 7


class TestPerRunWarmup:
    def test_no_warmup_happens_unless_it_is_switched_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NARRATEX_WARMUP", raising=False)
        service = FakeNarrationService()

        maybe_warmup_tts(
            service, voice=VOICE, book_id="bk", tts_engine=service.tts_engine
        )

        assert service.tts_engine.synthesized == []

    def test_a_warmup_utterance_is_synthesised_then_deleted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NARRATEX_WARMUP", "yes")
        service = FakeNarrationService(cache_repo=FakeCacheRepo(tmp_path))

        maybe_warmup_tts(
            service, voice=VOICE, book_id="bk", tts_engine=service.tts_engine
        )

        (call,) = service.tts_engine.synthesized
        assert call["text"] == "Warmup."
        assert call["output_path"].name == "__warmup.wav"
        assert not call["output_path"].exists()

    def test_a_warmup_file_that_cannot_be_deleted_is_left_alone(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NARRATEX_WARMUP", "true")
        service = FakeNarrationService(cache_repo=FakeCacheRepo(tmp_path))
        blocked = tmp_path / "bk" / VOICE.name / "__warmup.wav"
        blocked.mkdir(parents=True)

        maybe_warmup_tts(
            service, voice=VOICE, book_id="bk", tts_engine=service.tts_engine
        )

        assert blocked.is_dir()
        assert service._log.exceptions == []

    def test_a_failing_warmup_is_logged_and_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARRATEX_WARMUP", "1")
        service = FakeNarrationService(tts_engine=FakeEngine(fail=True))

        maybe_warmup_tts(
            service, voice=VOICE, book_id="bk", tts_engine=service.tts_engine
        )

        assert service._log.exceptions == ["Warmup synthesis failed"]


class TestStartupWarmup:
    def test_the_progress_bar_animates_then_settles(self, tmp_path: Path) -> None:
        service = FakeNarrationService(cache_repo=FakeCacheRepo(tmp_path))

        startup_warmup_tts(service, voice=VOICE, tts_engine=service.tts_engine)

        assert [s.status for s in service.states] == [
            NarrationStatus.SYNTHESIZING,
            NarrationStatus.IDLE,
        ]
        assert service.tts_engine.synthesized[0]["text"] == "."

    def test_a_startup_file_that_cannot_be_deleted_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        service = FakeNarrationService(cache_repo=FakeCacheRepo(tmp_path))
        blocked = tmp_path / "__startup__" / VOICE.name / "__startup_warmup.wav"
        blocked.mkdir(parents=True)

        startup_warmup_tts(service, voice=VOICE, tts_engine=service.tts_engine)

        assert blocked.is_dir()
        assert service.states[-1].status is NarrationStatus.IDLE

    def test_a_failing_startup_warmup_still_settles(self) -> None:
        service = FakeNarrationService(tts_engine=FakeEngine(fail=True))

        startup_warmup_tts(service, voice=VOICE, tts_engine=service.tts_engine)

        assert service.states[-1].status is NarrationStatus.IDLE


class TestAheadWindowGate:
    def test_a_chunk_inside_the_window_passes_straight_through(self) -> None:
        service = FakeNarrationService(_current_play_index=0)

        gate_synthesis_window(service, idx=1)  # must return promptly

    def test_playback_that_has_not_started_still_allows_a_head_start(self) -> None:
        service = FakeNarrationService(_current_play_index=-1)

        gate_synthesis_window(service, idx=2)

    def test_a_chunk_beyond_the_window_waits_until_stopped(self) -> None:
        service = FakeNarrationService(_current_play_index=0)
        waiter = threading.Thread(
            target=gate_synthesis_window, args=(service,), kwargs={"idx": 500}
        )
        waiter.start()

        assert waiter.is_alive()
        service._stop_event.set()
        waiter.join(timeout=5.0)

        assert not waiter.is_alive()

    def test_a_paused_service_allows_no_lead_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = FakeNarrationService(_current_play_index=3)
        service._pause_event.set()

        gate_synthesis_window(service, idx=3)


class TestSynthesisState:
    def test_the_playhead_survives_a_prefetch_update(self) -> None:
        service = FakeNarrationService(
            state=make_state(
                current_chunk_id=2,
                playback_chunk_id=2,
                audible_start=10,
                audible_end=20,
                highlight_start=10,
                highlight_end=20,
            )
        )

        set_synth_state(service, idx=4, total=10)

        assert service.state.status is NarrationStatus.SYNTHESIZING
        assert service.state.prefetch_chunk_id == 4
        assert service.state.playback_chunk_id == 2
        assert service.state.audible_start == 10
        assert service.state.message == "Preparing chunk 5/10"
        assert service.state.progress == pytest.approx(0.4)


class SlotOnceQueue:
    """A full queue that frees exactly one slot on the second attempt.

    Stands in for the real bounded queue at the moment playback consumes a
    chunk, which is when a waiting worker gets in.
    """

    def __init__(self) -> None:
        self.attempts = 0
        self.accepted: list[object] = []

    def put(self, item: object, timeout: float | None = None) -> None:
        del timeout
        self.attempts += 1
        if self.attempts == 1:
            raise queue.Full
        self.accepted.append(item)


class TestPutOrStop:
    """The put that a stop can interrupt.

    A plain blocking put on a bounded queue whose consumer has gone is
    unstoppable, which is how a worker outlives its run.
    """

    def test_an_item_goes_straight_through_when_there_is_room(self) -> None:
        path_q: queue.Queue = queue.Queue(maxsize=1)

        assert put_or_stop(path_q, Path("one.wav"), stop_event=threading.Event())
        assert path_q.get_nowait() == Path("one.wav")

    def test_a_full_queue_is_waited_on_rather_than_given_up_on(self) -> None:
        slot = SlotOnceQueue()

        assert put_or_stop(slot, Path("one.wav"), stop_event=threading.Event())
        assert slot.attempts == 2
        assert slot.accepted == [Path("one.wav")]

    def test_a_stopped_run_never_even_tries(self) -> None:
        stopped = threading.Event()
        stopped.set()
        slot = SlotOnceQueue()

        assert not put_or_stop(slot, Path("one.wav"), stop_event=stopped)
        assert slot.attempts == 0

    def test_a_queue_that_refuses_outright_is_not_retried(self) -> None:
        # Retrying a queue that raises something other than Full would spin
        # until the run stops, which is the behaviour being avoided.
        class Refusing:
            def put(self, item: object, timeout: float | None = None) -> None:
                del item, timeout
                raise Boom("put")

        assert not put_or_stop(
            Refusing(), Path("one.wav"), stop_event=threading.Event()
        )


class TestSignalEndOfStream:
    def test_the_marker_goes_in_without_waiting_when_there_is_room(self) -> None:
        path_q: queue.Queue = queue.Queue(maxsize=1)

        signal_end_of_stream(path_q, stop_event=threading.Event())

        assert path_q.get_nowait() is None

    def test_a_full_queue_is_waited_on_for_the_marker(self) -> None:
        # Playback reads until the marker arrives, so a slot is worth waiting
        # for; one that will never come is not.
        slot = SlotOnceQueue()

        signal_end_of_stream(slot, stop_event=threading.Event())

        assert slot.accepted == [None]

    def test_a_stopped_run_does_not_wait_for_the_marker(self) -> None:
        stopped = threading.Event()
        stopped.set()
        slot = SlotOnceQueue()

        signal_end_of_stream(slot, stop_event=stopped)

        assert slot.accepted == []
