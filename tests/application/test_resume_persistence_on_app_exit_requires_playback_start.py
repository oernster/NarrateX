from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.dto.narration_state import NarrationState, NarrationStatus
from voice_reader.application.services.narration.audio_playback import play
from voice_reader.application.services.narration.persistence import (
    maybe_save_resume_position,
)


@dataclass
class _FakeBookmarkService:
    calls: list[tuple[str, int, int]]

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        self.calls.append((str(book_id), int(char_offset), int(chunk_index)))


@dataclass
class _FakeStreamer:
    def start(
        self,
        *,
        chunk_audio_paths,
        on_chunk_start=None,
        on_chunk_end=None,
        on_playback_progress=None,
    ) -> None:
        # Consume one path to simulate real startup, then trigger chunk-start.
        _ = next(iter(chunk_audio_paths), None)
        if callable(on_chunk_start):
            on_chunk_start(0)

    def stop(self) -> None:
        return


@dataclass
class _FakeService:
    bookmark_service: _FakeBookmarkService
    audio_streamer: _FakeStreamer

    def __post_init__(self) -> None:
        self._persist_resume = True
        self._played_any_chunk = False
        self._chunks = [type("C", (), {"start_char": 100})()]
        self._book = type("B", (), {"id": "book-1"})()
        self._log = type("L", (), {"exception": lambda *_args, **_kwargs: None})()
        self._start_playback_index = 0
        self._current_play_index = -1
        self._stop_event = type("E", (), {"is_set": lambda _self: False})()
        self._stop_after_current_chunk = type(
            "E", (), {"is_set": lambda _self: False, "clear": lambda _self: None}
        )()
        self._pause_event = type("E", (), {"is_set": lambda _self: False})()
        self._state = NarrationState(
            status=NarrationStatus.SYNTHESIZING,
            current_chunk_id=None,
            playback_chunk_id=None,
            prefetch_chunk_id=None,
            total_chunks=1,
            progress=0.0,
            message="Preparing",
            audible_start=None,
            audible_end=None,
            highlight_start=None,
            highlight_end=None,
        )

        # Minimal no-op mapper used by resolve_playback_index_for_char_offset.
        self.sanitized_text_mapper = type(
            "M",
            (),
            {
                "sanitize_with_mapping": lambda _self, original_text: type(
                    "R", (), {"speak_text": str(original_text), "speak_to_original": []}
                )()
            },
        )()

    @property
    def state(self) -> NarrationState:
        return self._state

    def _set_state(self, state: NarrationState) -> None:
        self._state = state

    def current_position(self):
        return None, None


def test_app_exit_persists_resume_only_after_playback_started() -> None:
    bs = _FakeBookmarkService(calls=[])
    svc = _FakeService(bookmark_service=bs, audio_streamer=_FakeStreamer())

    # Before playback starts, exit should NOT create a JSON.
    maybe_save_resume_position(svc)  # type: ignore[arg-type]
    assert bs.calls == []

    # Simulate playback start via audio_playback callback, which marks _played_any_chunk.
    play(
        svc,  # type: ignore[arg-type]
        candidates=[
            type(
                "Cand",
                (),
                {
                    "chunk": type("TC", (), {"start_char": 100, "end_char": 120})(),
                    "speak_text": "Hello",
                    "speak_to_original": [],
                    "audio_path": None,
                },
            )()
        ],
        stream=type(
            "S", (), {"path_q": type("Q", (), {"get": lambda _self: None})()}
        )(),
        voice=type("V", (), {})(),
        book_id="book-1",
    )  # type: ignore[arg-type]

    maybe_save_resume_position(svc)  # type: ignore[arg-type]
    assert bs.calls, "Expected resume save after at least one chunk started"
