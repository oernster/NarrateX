"""The two synthesis strategies, each of which owns a thread's lifetime.

Both start real threads and both are driven here through their own events, so
nothing waits on a sleep and nothing is left running when a test returns. The
events are scripted rather than set from the test thread, which is what makes
a worker stop at an exact line instead of an approximate one.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

from tests.application.narration_fakes import (
    Boom,
    FakeEngine,
    FakeNarrationService,
    make_chunks,
)
from voice_reader.application.services.narration import (
    synthesis_parallel_kokoro as parallel_module,
    synthesis_sequential as sequential_module,
)
from voice_reader.application.services.narration._types import PlaybackCandidate
from voice_reader.application.services.narration.synthesis_parallel_kokoro import (
    start_parallel_kokoro_synthesis,
)
from voice_reader.application.services.narration.synthesis_sequential import (
    start_sequential_synthesis,
)
from voice_reader.domain.entities.voice_profile import VoiceProfile

_VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
_BOOK_ID = "book-cache-id"
_TIMEOUT_SECONDS = 5.0


class ScriptedEvent:
    """An event whose answers are written in advance.

    Answers are handed out in order and the last one repeats, so a thread can
    be stopped at an exact line without a sleep or a race. `worker_only` limits
    the script to the Kokoro worker: the publisher thread runs beside it and
    would otherwise consume answers in an order no test can predict.
    """

    _WORKER_THREAD_PREFIX = "tts-kokoro"

    def __init__(
        self,
        *answers: bool,
        worker_only: bool = False,
        elsewhere: bool = False,
    ) -> None:
        self._answers = list(answers)
        self._worker_only = worker_only
        self._elsewhere = elsewhere
        self._lock = threading.Lock()
        self.asked = 0

    def is_set(self) -> bool:
        name = threading.current_thread().name
        if self._worker_only and not name.startswith(self._WORKER_THREAD_PREFIX):
            return self._elsewhere
        with self._lock:
            self.asked += 1
            if len(self._answers) > 1:
                return self._answers.pop(0)
            return bool(self._answers[0]) if self._answers else False


class RefusingQueue:
    """A queue that accepts nothing, so both puts in the shutdown path run."""

    def __init__(self) -> None:
        self.refusals = 0

    def put_nowait(self, item: object) -> None:
        del item
        self.refusals += 1
        raise Boom("put_nowait")

    def put(self, item: object) -> None:
        del item
        self.refusals += 1
        raise Boom("put")

    def qsize(self) -> int:
        return 0


class QueueModule:
    """Stands in for the `queue` module.

    The path queue is the only one built with a maxsize, so that is the one
    replaced; the work queue stays real because the workers depend on it.
    """

    def __init__(self, path_queue: RefusingQueue) -> None:
        self._path_queue = path_queue

    def Queue(self, maxsize: int = 0):
        return self._path_queue if maxsize else queue.Queue()


def _candidates(*texts: str) -> list[PlaybackCandidate]:
    return [
        PlaybackCandidate(
            chunk=chunk,
            speak_text=chunk.text,
            speak_to_original=list(range(len(chunk.text))),
            audio_path=Path(f"{chunk.chunk_id}.wav"),
        )
        for chunk in make_chunks(*texts)
    ]


def _service(**overrides) -> FakeNarrationService:
    service = FakeNarrationService(_current_play_index=0, **overrides)
    return service


def _drain(stream) -> None:
    """Wait for the strategy to finish, so no thread outlives the test."""

    assert stream.synth_done.wait(timeout=_TIMEOUT_SECONDS)


class TestSequential:
    def _start(self, service, *, candidates, engine):
        return start_sequential_synthesis(
            service,
            candidates=candidates,
            voice=_VOICE,
            book_id=_BOOK_ID,
            tts_engine=engine,
        )

    def test_every_chunk_is_synthesised_in_order(self) -> None:
        engine = FakeEngine()
        service = _service()

        stream = self._start(
            service, candidates=_candidates("One. ", "Two. "), engine=engine
        )
        _drain(stream)

        assert [call["text"] for call in engine.synthesized] == ["One. ", "Two. "]
        assert stream.synth_errors == []

    def test_a_chunk_already_in_the_cache_is_not_synthesised_again(self) -> None:
        engine = FakeEngine()
        service = _service()
        service.cache_repo.cached.add((_BOOK_ID, _VOICE.name, 0))

        stream = self._start(
            service, candidates=_candidates("One. ", "Two. "), engine=engine
        )
        _drain(stream)

        assert [call["text"] for call in engine.synthesized] == ["Two. "]

    def test_a_stop_before_the_first_chunk_synthesises_nothing(self) -> None:
        # Stopping is checked before the chunk rather than after it, so a stop
        # that lands between books costs no synthesis at all.
        engine = FakeEngine()
        service = _service()
        service._stop_event.set()

        stream = self._start(service, candidates=_candidates("One. "), engine=engine)
        _drain(stream)

        assert engine.synthesized == []
        assert stream.path_q.get(timeout=_TIMEOUT_SECONDS) is None

    def test_the_end_marker_is_given_up_on_when_the_queue_refuses_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Playback reads the queue until the end marker arrives. If the queue
        # will not take it, the worker must still finish rather than hang.
        refusing = RefusingQueue()
        monkeypatch.setattr(sequential_module, "queue", QueueModule(refusing))
        service = _service()

        stream = self._start(service, candidates=[], engine=FakeEngine())
        _drain(stream)

        assert refusing.refusals == 2
        assert stream.synth_errors == []


class TestParallelKokoro:
    def _start(self, service, *, candidates, engine, workers=1):
        return start_parallel_kokoro_synthesis(
            service,
            candidates=candidates,
            voice=_VOICE,
            book_id=_BOOK_ID,
            tts_engine=engine,
            workers=workers,
        )

    def test_every_chunk_is_published_in_order(self) -> None:
        engine = FakeEngine()
        service = _service()
        candidates = _candidates("One. ", "Two. ", "Three.")

        stream = self._start(service, candidates=candidates, engine=engine, workers=2)
        published = [stream.path_q.get(timeout=_TIMEOUT_SECONDS) for _ in range(3)]
        _drain(stream)

        assert published == [c.audio_path for c in candidates]
        assert len(engine.synthesized) == 3

    def test_a_stop_inside_the_synthesis_window_abandons_the_chunk(self) -> None:
        engine = FakeEngine()
        service = _service()
        service._stop_event = ScriptedEvent(
            False, False, True, worker_only=True, elsewhere=True
        )

        stream = self._start(service, candidates=_candidates("One. "), engine=engine)
        _drain(stream)

        assert engine.synthesized == []

    def test_a_stop_while_paused_abandons_the_chunk(self) -> None:
        engine = FakeEngine()
        service = _service()
        service._stop_event = ScriptedEvent(
            False, False, False, True, worker_only=True, elsewhere=True
        )

        stream = self._start(service, candidates=_candidates("One. "), engine=engine)
        _drain(stream)

        assert engine.synthesized == []

    def test_a_pause_holds_synthesis_back_from_running_ahead(self) -> None:
        # A paused reader must not have the whole book synthesised behind it.
        # The worker waits while the chunk it holds is ahead of the playhead.
        engine = FakeEngine()
        service = _service()
        service._pause_event = ScriptedEvent(False, False, False, True, True, False)

        stream = self._start(
            service, candidates=_candidates("One. ", "Two. "), engine=engine
        )
        _drain(stream)

        assert [call["text"] for call in engine.synthesized] == ["One. ", "Two. "]
        assert service._pause_event.asked >= 6

    def test_the_end_marker_is_given_up_on_when_the_queue_refuses_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        refusing = RefusingQueue()
        monkeypatch.setattr(parallel_module, "queue", QueueModule(refusing))
        service = _service()

        stream = self._start(service, candidates=[], engine=FakeEngine())
        _drain(stream)

        assert refusing.refusals == 2
        assert stream.synth_errors == []
