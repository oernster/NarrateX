"""Saving the resume position.

Two rules shape this: no resume file is written for a book the user never
actually listened to, and a failure to save must never break playback.
"""

from __future__ import annotations

import pytest

from tests.application.narration_fakes import (
    Boom,
    FakeBook,
    FakeBookmarkService,
    FakeNarrationService,
    make_chunks,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration import persistence
from voice_reader.application.services.narration.persistence import (
    maybe_save_resume_position,
)
from voice_reader.domain.entities.text_chunk import TextChunk


class UnreadableState:
    """A state whose status cannot be read, to force the inference handler."""

    audible_start = None
    highlight_start = None
    playback_chunk_id = None
    current_chunk_id = None

    @property
    def status(self):
        raise Boom("status")


def _service(**kwargs) -> FakeNarrationService:
    kwargs.setdefault("_book", FakeBook(normalized_text="text"))
    return FakeNarrationService(**kwargs)


class TestNothingIsSaved:
    def test_a_service_asked_not_to_persist_saves_nothing(self) -> None:
        service = _service(_persist_resume=False, state=make_state(audible_start=1))

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []

    def test_no_bookmark_service_means_nothing_to_save_to(self) -> None:
        service = _service(bookmark_service=None, state=make_state(audible_start=1))

        maybe_save_resume_position(service)  # must not raise

    def test_no_loaded_book_saves_nothing(self) -> None:
        service = FakeNarrationService(state=make_state(audible_start=1))
        service._book = None

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []

    def test_a_book_that_was_never_played_saves_nothing(self) -> None:
        service = _service(state=make_state(status=NarrationStatus.IDLE))

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []

    def test_an_unreadable_state_counts_as_never_played(self) -> None:
        service = _service()
        service.state = UnreadableState()

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []


class TestWhatIsSaved:
    def test_the_audible_offset_is_preferred(self) -> None:
        service = _service(
            _chunks=make_chunks("one ", "two "),
            state=make_state(audible_start=5, playback_chunk_id=0),
        )

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved[0]["char_offset"] == 5
        assert service.bookmark_service.saved[0]["book_id"] == "book-1"

    def test_the_highlight_offset_is_used_when_nothing_is_audible(self) -> None:
        service = _service(
            _chunks=make_chunks("one ", "two "),
            state=make_state(highlight_start=6, playback_chunk_id=0),
        )

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved[0]["char_offset"] == 6

    def test_a_failure_resolving_the_index_still_saves_at_the_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def exploding(*args, **kwargs):
            raise Boom("resolve")

        monkeypatch.setattr(
            persistence, "resolve_playback_index_for_char_offset", exploding
        )
        service = _service(
            _chunks=make_chunks("one "), state=make_state(audible_start=5)
        )

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved[0]["chunk_index"] == 0

    def test_playback_with_no_state_falls_back_to_the_first_chunk(self) -> None:
        service = _service(_chunks=make_chunks("one ", "two "), _played_any_chunk=True)

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved[0] == {
            "book_id": "book-1",
            "char_offset": 0,
            "chunk_index": 0,
        }

    def test_an_unusable_first_chunk_abandons_the_save(self) -> None:
        broken = TextChunk(chunk_id=0, text="one", start_char="nope", end_char=3)
        service = _service(_chunks=[broken], _played_any_chunk=True)

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []

    def test_no_chunks_at_all_abandons_the_save(self) -> None:
        service = _service(_played_any_chunk=True)

        maybe_save_resume_position(service)

        assert service.bookmark_service.saved == []


class TestSavingCannotBreakPlayback:
    def test_a_failing_save_is_logged_and_swallowed(self) -> None:
        service = _service(
            _chunks=make_chunks("one "),
            state=make_state(audible_start=5, playback_chunk_id=0),
            bookmark_service=FakeBookmarkService(fail=True),
        )

        maybe_save_resume_position(service)

        assert service._log.exceptions == ["Failed saving resume position"]
