"""Three small narration helpers: where playback is, what to cache it under,
and which chunks are worth speaking at all.

None of them touches audio or a thread, so they are ordinary unit tests against
a hand-written stand-in for the service.
"""

from __future__ import annotations

import pytest

from tests.application.narration_fakes import (
    FakeBook,
    FakeEngine,
    FakeMapper,
    FakeNarrationService,
    make_chunks,
    make_state,
)
from voice_reader.application.services.narration.cache_key import (
    compute_book_cache_id,
)
from voice_reader.application.services.narration.candidates import (
    build_playback_candidates,
)
from voice_reader.application.services.narration.position import current_position
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.voice_profile import VoiceProfile


class TestCurrentPosition:
    def test_nothing_playing_gives_no_position(self) -> None:
        service = FakeNarrationService()

        assert current_position(service) == (None, None)

    def test_the_playback_chunk_is_offset_by_the_start_index(self) -> None:
        service = FakeNarrationService(
            state=make_state(playback_chunk_id=2, audible_start=500),
            _start_playback_index=10,
        )

        assert current_position(service) == (12, 500)

    def test_the_legacy_chunk_id_is_used_when_there_is_no_playback_one(self) -> None:
        service = FakeNarrationService(
            state=make_state(current_chunk_id=3, audible_start=7),
            _start_playback_index=1,
        )

        assert current_position(service) == (4, 7)

    def test_the_legacy_highlight_offset_is_used_when_nothing_is_audible(self) -> None:
        service = FakeNarrationService(
            state=make_state(playback_chunk_id=0, highlight_start=42)
        )

        assert current_position(service) == (0, 42)

    def test_the_chunk_start_is_used_when_no_offset_is_known(self) -> None:
        service = FakeNarrationService(
            state=make_state(playback_chunk_id=1),
            _chunks=make_chunks("first ", "second "),
        )

        assert current_position(service) == (1, len("first "))

    def test_an_unresolvable_chunk_gives_the_index_without_an_offset(self) -> None:
        service = FakeNarrationService(
            state=make_state(playback_chunk_id=9), _chunks=make_chunks("only ")
        )

        assert current_position(service) == (9, None)


class TestBookCacheId:
    def _service(
        self, text: str = "Chapter 1\n\nSome prose here.\n"
    ) -> FakeNarrationService:
        return FakeNarrationService(
            _book=FakeBook(
                normalized_text=text,
                document_model=plain_text.build_document(source=text),
            )
        )

    def test_an_already_computed_key_is_returned_unchanged(self) -> None:
        service = FakeNarrationService(_cache_book_id="cafebabecafebabe")

        assert compute_book_cache_id(service) == "cafebabecafebabe"

    def test_no_loaded_book_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="Book not loaded"):
            compute_book_cache_id(FakeNarrationService())

    def test_the_reading_start_is_resolved_when_it_is_not_known_yet(self) -> None:
        service = self._service()

        key = compute_book_cache_id(service)

        assert service._start_char is not None
        assert len(key) == 16
        assert service._cache_book_id == key

    def test_the_same_book_and_engine_give_the_same_key(self) -> None:
        first = compute_book_cache_id(self._service())
        second = compute_book_cache_id(self._service())

        assert first == second

    def test_a_different_engine_gives_a_different_key(self) -> None:
        service = self._service()
        service.tts_engine = FakeEngine("Another Engine")

        assert compute_book_cache_id(service) != compute_book_cache_id(self._service())

    def test_different_text_gives_a_different_key(self) -> None:
        other = self._service(text="Chapter 2\n\nDifferent prose.\n")

        assert compute_book_cache_id(other) != compute_book_cache_id(self._service())


class TestPlaybackCandidates:
    VOICE = VoiceProfile(name="narrator", reference_audio_paths=())

    def test_one_candidate_is_built_per_speakable_chunk(self) -> None:
        service = FakeNarrationService(_chunks=make_chunks("Hello. ", "World. "))

        built = build_playback_candidates(service, voice=self.VOICE, book_id="bk")

        assert [c.speak_text for c in built] == ["Hello. ", "World. "]
        assert [c.audio_path.name for c in built] == ["0.wav", "1.wav"]
        assert built[0].audio_path.parts[:3] == ("audio-cache", "bk", "narrator")

    def test_a_chunk_with_nothing_to_say_is_skipped(self) -> None:
        service = FakeNarrationService(
            _chunks=make_chunks("...", "Real words. "),
            sanitized_text_mapper=FakeMapper(silent_for={"..."}),
        )

        built = build_playback_candidates(service, voice=self.VOICE, book_id="bk")

        assert [c.speak_text for c in built] == ["Real words. "]

    def test_no_chunks_gives_no_candidates(self) -> None:
        service = FakeNarrationService()

        assert build_playback_candidates(service, voice=self.VOICE, book_id="bk") == []
