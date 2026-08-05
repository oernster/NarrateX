"""Driving the audio streamer and turning its callbacks into reader state.

The stand-in streamer records the three callbacks instead of opening a device,
so each one can be driven on its own and the resulting state inspected.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from tests.application.narration_fakes import (
    FakeNarrationService,
    FakeSynchronizer,
    make_chunks,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration._types import PlaybackCandidate
from voice_reader.application.services.narration.audio_playback import play
from voice_reader.application.services.narration.synthesis_common import (
    SynthesisStream,
)
from voice_reader.domain.entities.voice_profile import VoiceProfile

VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
BOOK_ID = "bk"


def _candidates(count: int = 2) -> list[PlaybackCandidate]:
    chunks = make_chunks(*[f"Chunk {i}. " for i in range(count)])
    return [
        PlaybackCandidate(
            chunk=c,
            speak_text=c.text,
            speak_to_original=list(range(len(c.text))),
            audio_path=Path(f"{i}.wav"),
        )
        for i, c in enumerate(chunks)
    ]


def _stream(*paths: Path | None) -> SynthesisStream:
    q: "queue.Queue[Path | None]" = queue.Queue()
    for p in paths:
        q.put(p)
    return SynthesisStream(path_q=q, synth_done=threading.Event(), synth_errors=[])


def _play(service: FakeNarrationService, *, count: int = 2, paths=(None,)):
    play(
        service,
        candidates=_candidates(count),
        stream=_stream(*paths),
        voice=VOICE,
        book_id=BOOK_ID,
    )
    return service.audio_streamer


class TestThePathIterator:
    def test_paths_are_handed_over_until_the_end_marker(self) -> None:
        service = FakeNarrationService()

        streamer = _play(service, paths=(Path("a.wav"), Path("b.wav"), None))

        assert streamer.paths == [Path("a.wav"), Path("b.wav")]

    def test_a_stopped_service_hands_over_nothing(self) -> None:
        service = FakeNarrationService()
        service._stop_event.set()

        streamer = _play(service, paths=(Path("a.wav"), None))

        assert streamer.paths == []


class TestChunkStart:
    def test_starting_a_chunk_announces_it_and_marks_playback_begun(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)

        streamer.on_chunk_start(1)

        assert service._played_any_chunk is True
        assert service._current_play_index == 1
        assert service.state.status is NarrationStatus.PLAYING
        assert service.state.playback_chunk_id == 1
        assert service.state.message == "Playing chunk 2/2"

    def test_an_index_outside_the_book_announces_nothing(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)

        streamer.on_chunk_start(99)

        assert service._current_play_index == 99
        assert service.states == []


class TestChunkEnd:
    def test_an_ordinary_chunk_end_changes_nothing(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)

        streamer.on_chunk_end(0)

        assert not service._stop_event.is_set()

    def test_a_pending_stop_request_is_honoured_at_the_chunk_boundary(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)
        service._stop_after_current_chunk.set()

        streamer.on_chunk_end(0)

        assert service._stop_event.is_set()
        assert not service._stop_after_current_chunk.is_set()
        assert "stop" in streamer.events


class TestProgress:
    def test_progress_moves_the_audible_span(self) -> None:
        service = FakeNarrationService(playback_synchronizer=FakeSynchronizer((5, 9)))
        streamer = _play(service)

        streamer.on_playback_progress(0, 100)

        assert (service.state.audible_start, service.state.audible_end) == (5, 9)
        assert service.state.playback_chunk_id == 0

    def test_an_index_outside_the_book_is_ignored(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)

        streamer.on_playback_progress(99, 100)

        assert service.states == []

    def test_updates_closer_together_than_the_throttle_are_dropped(self) -> None:
        service = FakeNarrationService(playback_synchronizer=FakeSynchronizer((5, 9)))
        streamer = _play(service)

        streamer.on_playback_progress(0, 100)
        before = len(service.states)
        streamer.on_playback_progress(0, 110)

        assert len(service.states) == before

    def test_an_unreadable_throttle_marker_does_not_stop_the_update(self) -> None:
        service = FakeNarrationService(playback_synchronizer=FakeSynchronizer((5, 9)))
        streamer = _play(service)
        streamer.on_playback_progress._last_emit_ms = "not a number"

        streamer.on_playback_progress(0, 100)

        assert service.state.audible_start == 5

    def test_a_paused_service_stops_emitting(self) -> None:
        service = FakeNarrationService()
        streamer = _play(service)
        service._pause_event.set()

        streamer.on_playback_progress(0, 100)

        assert service.states == []

    def test_an_unresolvable_span_falls_back_to_the_whole_chunk(self) -> None:
        service = FakeNarrationService(
            playback_synchronizer=FakeSynchronizer((None, None))
        )
        streamer = _play(service)

        streamer.on_playback_progress(0, 100)

        chunk = _candidates()[0].chunk
        assert service.state.audible_start == chunk.start_char
        assert service.state.audible_end == chunk.end_char

    def test_an_unchanged_span_is_not_re_emitted(self) -> None:
        service = FakeNarrationService(playback_synchronizer=FakeSynchronizer((5, 9)))
        service.state = make_state(playback_chunk_id=0, audible_start=5, audible_end=9)
        streamer = _play(service)

        streamer.on_playback_progress(0, 100)

        assert service.states == []
