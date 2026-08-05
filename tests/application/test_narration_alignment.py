"""Resolving which characters are being spoken right now.

A stored alignment is used when there is one. Otherwise the span is estimated,
timed against the real audio file when it can be read, and the estimate is
written back so the next pass is cheap. Every step degrades rather than raises,
because losing the highlight must not stop playback.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from tests.application.narration_fakes import (
    FakeAlignmentIO,
    FakeCacheRepo,
    FakeNarrationService,
    FakeSynchronizer,
    make_chunks,
)
from voice_reader.application.services.narration.alignment import resolve_audible_span
from voice_reader.domain.alignment.model import ChunkAlignment
from voice_reader.domain.entities.voice_profile import VoiceProfile

VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
BOOK_ID = "bk"
SAMPLE_RATE = 8000


def _service(tmp_path: Path, **kwargs) -> FakeNarrationService:
    kwargs.setdefault("cache_repo", FakeCacheRepo(tmp_path))
    return FakeNarrationService(_chunks=make_chunks("Hello there. "), **kwargs)


def _resolve(service: FakeNarrationService, *, maps=None, chunk_local_ms: int = 250):
    chunk = service._chunks[0]
    return resolve_audible_span(
        service,
        chunk=chunk,
        play_index=0,
        chunk_local_ms=chunk_local_ms,
        playback_text_maps=(
            maps if maps is not None else [(chunk.text, list(range(len(chunk.text))))]
        ),
        book_id=BOOK_ID,
        voice=VOICE,
    )


def _write_wav(path: Path, *, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(SAMPLE_RATE * seconds)
    sf.write(str(path), np.zeros(frames, dtype="float32"), SAMPLE_RATE)


class TestStoredAlignment:
    def test_a_stored_alignment_is_used_as_it_stands(self, tmp_path: Path) -> None:
        stored = ChunkAlignment(chunk_id=0, duration_ms=1234, spans=[])
        service = _service(
            tmp_path,
            alignment_io=FakeAlignmentIO(loaded=stored),
            playback_synchronizer=FakeSynchronizer((3, 4)),
        )
        alignment_path = service.cache_repo.alignment_path(
            book_id=BOOK_ID, voice_name=VOICE.name, chunk_id=0
        )
        alignment_path.parent.mkdir(parents=True, exist_ok=True)
        alignment_path.write_text("{}", encoding="utf-8")

        assert _resolve(service) == (3, 4)
        assert service.playback_synchronizer.seen == [stored]
        assert service.estimated_aligner.calls == []

    def test_a_failure_reading_the_stored_alignment_falls_back_to_estimating(
        self, tmp_path: Path
    ) -> None:
        service = _service(
            tmp_path, cache_repo=FakeCacheRepo(tmp_path, fail_paths=True)
        )

        assert _resolve(service) == (1, 2)
        assert service.estimated_aligner.calls


class TestEstimating:
    def test_the_estimate_is_timed_against_the_real_audio_when_it_exists(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)
        _write_wav(
            service.cache_repo.audio_path(
                book_id=BOOK_ID, voice_name=VOICE.name, chunk_id=0
            ),
            seconds=0.5,
        )

        _resolve(service, chunk_local_ms=1)

        assert service.estimated_aligner.calls[0]["duration_ms"] == 500

    def test_a_missing_audio_file_falls_back_to_the_reported_position(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)

        _resolve(service, chunk_local_ms=321)

        assert service.estimated_aligner.calls[0]["duration_ms"] == 321

    def test_a_missing_text_map_estimates_against_empty_text(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)

        _resolve(service, maps=[])

        assert service.estimated_aligner.calls[0]["speak_text"] == ""

    def test_the_estimate_is_written_back_in_book_coordinates(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)

        _resolve(service)

        ((_path, saved),) = service.alignment_io.saved
        assert saved.chunk_id == 0
        assert [(s.start_char, s.end_char) for s in saved.spans] == [
            (0, len("Hello there. "))
        ]

    def test_a_failure_writing_the_estimate_back_is_swallowed(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path, alignment_io=FakeAlignmentIO(fail_save=True))

        assert _resolve(service) == (1, 2)
        assert service.alignment_io.saved == []
