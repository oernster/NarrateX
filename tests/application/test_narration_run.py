"""The narration run loop.

`run` decides how a book is synthesised (one worker in order versus the Kokoro
worker pool), waits for a prefetch window, then hands over to playback and
reports how the session ended. Its three collaborators are substituted at the
module boundary, so those decisions can be read without starting a worker
thread or touching an audio device.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

from tests.application.narration_fakes import (
    Boom,
    FakeBook,
    FakeEngine,
    FakeNarrationService,
    make_chunks,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration import run as run_module
from voice_reader.application.services.narration._types import PlaybackCandidate
from voice_reader.application.services.narration.synthesis_common import SynthesisStream
from voice_reader.domain.entities.voice_profile import VoiceProfile

_VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
_SEQUENTIAL = "sequential"
_PARALLEL = "parallel"


class WrappedKokoroEngine(FakeEngine):
    """An engine that delegates to Kokoro rather than being Kokoro itself."""

    def __init__(self) -> None:
        super().__init__("Piper")
        self.native_engine = FakeEngine("Kokoro")


class UninspectableVoice:
    """A voice that raises when asked what it is, so the guard has to hold."""

    name = "broken"

    @property
    def reference_audio_paths(self):
        raise Boom("reference_audio_paths")


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


def _finished_stream(*, errors: list[BaseException] | None = None) -> SynthesisStream:
    """A stream that has already synthesised everything it is going to."""

    done = threading.Event()
    done.set()
    return SynthesisStream(
        path_q=queue.Queue(),
        synth_done=done,
        synth_errors=list(errors or []),
    )


class Harness:
    """Records which synthesis strategy `run` chose and what it played."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        stream: SynthesisStream | None = None,
        candidates: list[PlaybackCandidate] | None = None,
    ) -> None:
        self.stream = stream if stream is not None else _finished_stream()
        self.candidates = (
            candidates if candidates is not None else _candidates("One. ", "Two. ")
        )
        self.strategy: str | None = None
        self.workers: int | None = None
        self.played: list[PlaybackCandidate] = []

        monkeypatch.setattr(run_module, "build_playback_candidates", self._build)
        monkeypatch.setattr(run_module, "start_sequential_synthesis", self._sequential)
        monkeypatch.setattr(run_module, "start_parallel_kokoro_synthesis", self._pool)
        monkeypatch.setattr(run_module, "play", self._play)

    def _build(self, service, *, voice, book_id) -> list[PlaybackCandidate]:
        del service, voice, book_id
        return list(self.candidates)

    def _sequential(self, service, **kwargs) -> SynthesisStream:
        del service, kwargs
        self.strategy = _SEQUENTIAL
        return self.stream

    def _pool(self, service, *, workers, **kwargs) -> SynthesisStream:
        del service, kwargs
        self.strategy = _PARALLEL
        self.workers = int(workers)
        return self.stream

    def _play(self, service, *, candidates, stream, voice, book_id) -> None:
        del service, stream, voice, book_id
        self.played = list(candidates)


def _service(*, voice: object = _VOICE, engine: object | None = None):
    service = FakeNarrationService(
        _book=FakeBook(normalized_text="One. Two. "),
        _voice=voice,
        _chunks=make_chunks("One. ", "Two. "),
    )
    if engine is not None:
        service.tts_engine = engine
    return service


class TestStrategyChoice:
    def test_one_worker_synthesises_in_order(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.delenv("NARRATEX_KOKORO_WORKERS", raising=False)

        run_module.run(_service())

        assert harness.strategy == _SEQUENTIAL

    def test_a_worker_count_that_is_not_a_number_is_ignored(self, monkeypatch) -> None:
        # The variable is user-supplied. A typo must not stop a book playing.
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "two")

        run_module.run(_service(engine=FakeEngine("Kokoro")))

        assert harness.strategy == _SEQUENTIAL

    def test_kokoro_with_several_workers_uses_the_pool(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "3")

        run_module.run(_service(engine=FakeEngine("Kokoro")))

        assert harness.strategy == _PARALLEL
        assert harness.workers == 3

    def test_an_engine_wrapping_kokoro_also_uses_the_pool(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "2")

        run_module.run(_service(engine=WrappedKokoroEngine()))

        assert harness.strategy == _PARALLEL

    def test_an_engine_wrapping_something_else_does_not(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "2")
        engine = FakeEngine("Piper")
        engine.native_engine = FakeEngine("Piper Native")

        run_module.run(_service(engine=engine))

        assert harness.strategy == _SEQUENTIAL

    def test_a_voice_that_cannot_be_inspected_falls_back(self, monkeypatch) -> None:
        # Cloned-voice detection decides the strategy. If it cannot be decided,
        # the safe answer is the one that works for every engine.
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "2")

        run_module.run(_service(voice=UninspectableVoice()))

        assert harness.strategy == _SEQUENTIAL

    def test_a_cloned_voice_never_uses_the_pool(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_KOKORO_WORKERS", "2")
        cloned = VoiceProfile(name="cloned", reference_audio_paths=(Path("a.wav"),))

        run_module.run(_service(voice=cloned, engine=FakeEngine("Kokoro")))

        assert harness.strategy == _SEQUENTIAL


class TestPrefetch:
    def test_a_prefetch_count_that_is_not_a_number_is_ignored(
        self, monkeypatch
    ) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_PREFETCH_CHUNKS", "lots")

        run_module.run(_service())

        assert len(harness.played) == 2

    def test_prefetch_can_be_switched_off(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        monkeypatch.setenv("NARRATEX_PREFETCH_CHUNKS", "0")

        run_module.run(_service())

        assert len(harness.played) == 2


class TestStartIndex:
    def test_playback_starts_at_the_requested_index(self, monkeypatch) -> None:
        harness = Harness(
            monkeypatch, candidates=_candidates("One. ", "Two. ", "Three.")
        )
        service = _service()
        service._start_playback_index = 2

        run_module.run(service)

        assert [c.speak_text for c in harness.played] == ["Three."]

    def test_an_index_past_the_end_leaves_nothing_to_play(self, monkeypatch) -> None:
        harness = Harness(monkeypatch)
        service = _service()
        service._start_playback_index = 99

        run_module.run(service)

        assert harness.played == []


class TestOutcome:
    def test_a_finished_book_ends_idle_and_complete(self, monkeypatch) -> None:
        Harness(monkeypatch)
        service = _service()

        run_module.run(service)

        assert service.state.status is NarrationStatus.IDLE
        assert service.state.progress == 1.0
        assert service.state.total_chunks == 2

    def test_a_stopped_book_ends_stopped_at_no_progress(self, monkeypatch) -> None:
        Harness(monkeypatch)
        service = _service()
        service._stop_event.set()

        run_module.run(service)

        assert service.state.status is NarrationStatus.STOPPED
        assert service.state.progress == 0.0
        assert service.state.total_chunks == 2
        assert service.state.current_chunk_id is None

    def test_a_synthesis_failure_surfaces_as_an_error(self, monkeypatch) -> None:
        # The worker records its failure rather than raising across the thread
        # boundary, so the run loop has to re-raise it to report anything.
        Harness(monkeypatch, stream=_finished_stream(errors=[Boom("synthesis")]))
        service = _service()

        run_module.run(service)

        assert service.state.status is NarrationStatus.ERROR
        assert "synthesis" in service.state.message
