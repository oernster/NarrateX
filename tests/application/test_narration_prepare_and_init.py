"""Preparing a run, and setting up the service's runtime state.

`prepare` decides where playback will begin: from an explicit index, from an
absolute character offset, or from the stored resume position. `init_runtime_state`
is the constructor's other half and must survive a preferences store or an audio
layer that will not answer.
"""

from __future__ import annotations

import pytest

from tests.application.narration_fakes import (
    FakeAudioStreamer,
    FakeBook,
    FakeBookmarkService,
    FakeMapper,
    FakeNarrationService,
    FakeNavigationChunkService,
    FakePreferencesRepo,
    FakeResumePosition,
    make_chunks,
)
from voice_reader.domain.entities.text_chunk import TextChunk
from voice_reader.application.services.narration.init import init_runtime_state
from voice_reader.application.services.narration.prepare import (
    prepare,
    resolve_playback_index_for_char_offset,
)
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
TEXT = "Chapter 1\n\nSome prose here.\n"


def _service(**kwargs) -> FakeNarrationService:
    kwargs.setdefault(
        "_book",
        FakeBook(
            normalized_text=TEXT, document_model=plain_text.build_document(source=TEXT)
        ),
    )
    kwargs.setdefault(
        "navigation_chunk_service",
        FakeNavigationChunkService(make_chunks("One. ", "Two. ", "Three. ")),
    )
    return FakeNarrationService(**kwargs)


class TestPrepare:
    def test_no_loaded_book_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="Book not loaded"):
            prepare(FakeNarrationService(), voice=VOICE)

    def test_an_explicit_index_is_taken_as_given(self) -> None:
        service = _service()

        prepare(service, voice=VOICE, start_playback_index=2)

        assert service._start_playback_index == 2
        assert service._voice is VOICE

    def test_a_negative_index_is_clamped_to_the_start(self) -> None:
        service = _service()

        prepare(service, voice=VOICE, start_playback_index=-4)

        assert service._start_playback_index == 0

    def test_a_start_offset_inside_a_chunk_trims_that_chunk(self) -> None:
        service = _service()

        prepare(service, voice=VOICE, start_char_offset=7)

        assert service._chunks[1].text == "o. "
        assert service._chunks[1].start_char == 7

    def test_a_start_offset_on_a_boundary_leaves_the_chunk_whole(self) -> None:
        service = _service()

        prepare(service, voice=VOICE, start_char_offset=5)

        assert service._chunks[1].text == "Two. "

    def test_a_start_offset_before_every_chunk_trims_nothing(self) -> None:
        late = TextChunk(chunk_id=0, text="One. ", start_char=100, end_char=105)
        service = _service(navigation_chunk_service=FakeNavigationChunkService([late]))

        prepare(service, voice=VOICE, start_char_offset=1)

        assert service._chunks[0].text == "One. "

    def test_the_stored_resume_offset_is_used_when_nothing_is_asked_for(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.resume = FakeResumePosition(char_offset=6)
        service = _service(bookmark_service=bookmarks)

        prepare(service, voice=VOICE)

        assert service._start_playback_index == 1
        assert service._persist_resume is True

    def test_a_resume_offset_past_every_chunk_starts_at_the_beginning(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.resume = FakeResumePosition(char_offset=9_999)
        service = _service(bookmark_service=bookmarks)

        prepare(service, voice=VOICE)

        assert service._start_playback_index == 0

    def test_no_chunks_at_all_leaves_the_index_at_the_beginning(self) -> None:
        service = _service(navigation_chunk_service=FakeNavigationChunkService([]))

        prepare(service, voice=VOICE, start_char_offset=3)

        assert service._start_playback_index == 0

    def test_chunks_with_nothing_to_say_leave_the_index_at_the_beginning(self) -> None:
        service = _service(
            navigation_chunk_service=FakeNavigationChunkService(make_chunks("...")),
            sanitized_text_mapper=FakeMapper(silent_for={"..."}),
        )

        prepare(service, voice=VOICE, start_char_offset=1)

        assert service._start_playback_index == 0

    def test_a_failing_resume_lookup_is_survivable(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.fail_load = True
        service = _service(bookmark_service=bookmarks)

        prepare(service, voice=VOICE)

        assert service._start_playback_index == 0

    def test_an_unreadable_resume_offset_is_survivable(self) -> None:
        class OddResume:
            char_offset = "not a number"

        bookmarks = FakeBookmarkService()
        bookmarks.resume = OddResume()
        service = _service(bookmark_service=bookmarks)

        prepare(service, voice=VOICE)

        assert service._start_playback_index == 0

    def test_persistence_can_be_switched_off_for_the_run(self) -> None:
        service = _service()

        prepare(service, voice=VOICE, persist_resume=False)

        assert service._persist_resume is False


class TestResolvingAnIndexForAnOffset:
    def test_no_chunks_maps_to_nothing(self) -> None:
        assert (
            resolve_playback_index_for_char_offset(
                FakeNarrationService(), char_offset=0, chunks=[]
            )
            is None
        )

    def test_chunks_with_nothing_to_say_map_to_nothing(self) -> None:
        service = FakeNarrationService(
            sanitized_text_mapper=FakeMapper(silent_for={"..."})
        )

        assert (
            resolve_playback_index_for_char_offset(
                service, char_offset=1, chunks=make_chunks("...")
            )
            is None
        )

    def test_an_offset_past_every_chunk_maps_to_nothing(self) -> None:
        assert (
            resolve_playback_index_for_char_offset(
                FakeNarrationService(),
                char_offset=9_999,
                chunks=make_chunks("One. ", "Two. "),
            )
            is None
        )


class TestInitRuntimeState:
    def test_the_defaults_are_pushed_into_the_audio_layer(self) -> None:
        service = FakeNarrationService(navigation_chunk_service=None)

        init_runtime_state(service)

        assert service.audio_streamer.events == ["rate", "volume"]
        assert service.navigation_chunk_service is not None
        assert service._persist_resume is True
        assert service._played_any_chunk is False

    def test_a_stored_volume_is_restored(self) -> None:
        stored = PlaybackVolume.default()
        service = FakeNarrationService(
            preferences_repo=FakePreferencesRepo(volume=stored)
        )

        init_runtime_state(service)

        assert service._volume is stored

    def test_a_failing_preferences_store_leaves_the_default_volume(self) -> None:
        service = FakeNarrationService(
            preferences_repo=FakePreferencesRepo(fail_volume=True)
        )

        init_runtime_state(service)

        assert service._volume == PlaybackVolume.default()

    def test_no_preferences_store_is_allowed(self) -> None:
        service = FakeNarrationService(preferences_repo=None)

        init_runtime_state(service)

        assert service._volume == PlaybackVolume.default()

    def test_an_audio_layer_that_refuses_the_rate_is_survivable(self) -> None:
        service = FakeNarrationService(audio_streamer=FakeAudioStreamer(fail_rate=True))

        init_runtime_state(service)

        assert service.audio_streamer.events == ["volume"]

    def test_an_audio_layer_that_refuses_the_volume_is_survivable(self) -> None:
        service = FakeNarrationService(
            audio_streamer=FakeAudioStreamer(fail_volume=True)
        )

        init_runtime_state(service)

        assert service.audio_streamer.events == ["rate"]
