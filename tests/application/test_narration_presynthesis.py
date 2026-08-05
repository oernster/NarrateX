"""Pre-synthesising the first chunks so pressing Play is near-instant.

The TTS engine is a hand-written stand-in, so nothing here loads a model or
opens a device. What is tested is where the run starts, what it skips and how
it gives up.
"""

from __future__ import annotations

import threading

import pytest

from tests.application.narration_fakes import (
    FakeBook,
    FakeBookmarkService,
    FakeEngine,
    FakeMapper,
    FakeNarrationService,
    FakeNavigationChunkService,
    FakeResumePosition,
    make_chunks,
)
from voice_reader.application.services.narration import cache_key
from voice_reader.application.services.narration.synthesis_common import (
    presynthesize_start_chunks,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.voice_profile import VoiceProfile

VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
TEXT = "Chapter 1\n\nSome prose here.\n"


def _book() -> FakeBook:
    return FakeBook(
        normalized_text=TEXT, document_model=plain_text.build_document(source=TEXT)
    )


class TestPreSynthesis:
    def _service(self, **kwargs) -> FakeNarrationService:
        kwargs.setdefault("_book", _book())
        kwargs.setdefault(
            "navigation_chunk_service",
            FakeNavigationChunkService(make_chunks("One. ", "Two. ", "Three. ")),
        )
        return FakeNarrationService(**kwargs)

    def test_the_first_chunks_are_synthesised_and_the_rest_left(self) -> None:
        service = self._service()

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == ["One. ", "Two. "]

    def test_an_already_cached_chunk_is_not_synthesised_again(self) -> None:
        service = self._service()
        service.cache_repo.cached.add(
            (
                "no-such-key",
                VOICE.name,
                0,
            )
        )

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
            n_chunks=1,
        )

        assert len(service.tts_engine.synthesized) == 1

    def test_no_book_means_nothing_to_pre_synthesise(self) -> None:
        service = FakeNarrationService()

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert service.tts_engine.synthesized == []

    def test_no_navigation_service_means_nothing_to_pre_synthesise(self) -> None:
        service = self._service(navigation_chunk_service=None)

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert service.tts_engine.synthesized == []

    def test_a_failure_building_chunks_abandons_the_attempt(self) -> None:
        service = self._service(
            navigation_chunk_service=FakeNavigationChunkService(fail=True)
        )

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert service.tts_engine.synthesized == []

    def test_a_resume_position_inside_a_chunk_starts_there(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.resume = FakeResumePosition(char_offset=6)
        service = self._service(bookmark_service=bookmarks)

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == [
            "Two. ",
            "Three. ",
        ]

    def test_a_resume_position_before_the_next_spoken_chunk_starts_there(self) -> None:
        # The first chunk is silent, so the search skips it; the second starts
        # after the resume offset rather than containing it.
        bookmarks = FakeBookmarkService()
        bookmarks.resume = FakeResumePosition(char_offset=3)
        service = self._service(
            bookmark_service=bookmarks,
            sanitized_text_mapper=FakeMapper(silent_for={"One. "}),
        )

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
            n_chunks=1,
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == ["Two. "]

    def test_a_failing_resume_lookup_starts_from_the_beginning(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.fail_load = True
        service = self._service(bookmark_service=bookmarks)

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
            n_chunks=1,
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == ["One. "]

    def test_an_uncomputable_cache_key_abandons_the_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def exploding(service):
            raise RuntimeError("cache key")

        monkeypatch.setattr(cache_key, "compute_book_cache_id", exploding)
        service = self._service(bookmark_service=None)

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert service.tts_engine.synthesized == []

    def test_a_cancelled_run_stops_immediately(self) -> None:
        service = self._service()
        cancelled = threading.Event()
        cancelled.set()

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=cancelled,
        )

        assert service.tts_engine.synthesized == []

    def test_a_chunk_with_nothing_to_say_is_skipped(self) -> None:
        service = self._service(sanitized_text_mapper=FakeMapper(silent_for={"One. "}))

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
            n_chunks=1,
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == ["Two. "]

    def test_a_failing_sanitiser_skips_that_chunk(self) -> None:
        class ExplodingMapper(FakeMapper):
            def sanitize_with_mapping(self, *, original_text: str):
                if original_text == "One. ":
                    raise RuntimeError("sanitise")
                return super().sanitize_with_mapping(original_text=original_text)

        service = self._service(sanitized_text_mapper=ExplodingMapper())

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
            n_chunks=1,
        )

        assert [c["text"] for c in service.tts_engine.synthesized] == ["Two. "]

    def test_a_failing_synthesis_abandons_the_rest(self) -> None:
        service = self._service(tts_engine=FakeEngine(fail=True))

        presynthesize_start_chunks(
            service,
            voice=VOICE,
            tts_engine=service.tts_engine,
            cancel_event=threading.Event(),
        )

        assert service.tts_engine.synthesized == []
