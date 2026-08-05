"""The narration service facade itself.

`NarrationService` holds no logic of its own: every method hands the whole
service to a function in `voice_reader.application.services.narration.*`. Those
functions are tested against a hand-written stand-in; these tests drive the
facade, so each delegation is exercised on the real service object and a method
that stops forwarding fails here rather than silently.
"""

from __future__ import annotations

import threading
from pathlib import Path

from tests.application.narration_fakes import (
    FakeAudioStreamer,
    FakeBook,
    FakeBookmarkService,
    FakeBookRepo,
    FakeCacheRepo,
    FakeChunkingService,
    FakeEngine,
    FakeNavigationChunkService,
    FakePreferencesRepo,
    make_chunks,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.domain.document import plain_text
from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.value_objects.playback_volume import PlaybackVolume

_TEXT = "Chapter 1\n\nOne. Two. Three.\n"
_VOICE = VoiceProfile(name="narrator", reference_audio_paths=())
_SOURCE = Path("a-book.epub")


def _book() -> FakeBook:
    return FakeBook(
        normalized_text=_TEXT,
        document_model=plain_text.build_document(source=_TEXT),
    )


def _service(**overrides) -> NarrationService:
    """A real service wired to stand-ins, so no device or thread is involved."""

    defaults = {
        "book_repo": FakeBookRepo(book=_book()),
        "cache_repo": FakeCacheRepo(),
        "tts_engine": FakeEngine(),
        "audio_streamer": FakeAudioStreamer(),
        "chunking_service": FakeChunkingService(chunks=make_chunks("One. ", "Two. ")),
        "device": "cpu",
        "language": "en",
        "bookmark_service": FakeBookmarkService(),
        "preferences_repo": FakePreferencesRepo(),
        "navigation_chunk_service": FakeNavigationChunkService(),
    }
    defaults.update(overrides)
    return NarrationService(**defaults)


class TestListeners:
    def test_a_listener_sees_every_state_change(self) -> None:
        service = _service()
        seen: list[NarrationStatus] = []
        service.add_listener(lambda state: seen.append(state.status))

        service.load_book(_SOURCE)

        assert NarrationStatus.LOADING in seen
        assert seen[-1] is NarrationStatus.IDLE

    def test_a_second_listener_is_told_as_well(self) -> None:
        service = _service()
        first: list[NarrationStatus] = []
        second: list[NarrationStatus] = []
        service.add_listener(lambda state: first.append(state.status))
        service.add_listener(lambda state: second.append(state.status))

        service.load_book(_SOURCE)

        assert first == second
        assert first


class TestVolume:
    def test_a_volume_change_is_persisted(self) -> None:
        preferences = FakePreferencesRepo()
        service = _service(preferences_repo=preferences)

        service.set_volume(PlaybackVolume(0.4))

        assert [v.multiplier for v in preferences.saved_volumes] == [0.4]
        assert service.playback_volume().multiplier == 0.4

    def test_a_failed_save_leaves_the_session_volume_set(self) -> None:
        # Persistence is a convenience. Losing it must not cost the user the
        # volume they just chose, nor raise into the UI.
        preferences = FakePreferencesRepo(fail_save_volume=True)
        service = _service(preferences_repo=preferences)

        service.set_volume(PlaybackVolume(0.4))

        assert preferences.saved_volumes == []
        assert service.playback_volume().multiplier == 0.4


class TestBookOwnership:
    def test_adopting_a_book_never_reparses_it(self) -> None:
        repository = FakeBookRepo(book=None)
        service = _service(book_repo=repository)
        book = _book()

        assert service.adopt_book(book, _SOURCE) is book
        assert service.loaded_book() is book
        assert service.loaded_book_id() == book.id
        assert repository.loaded == []

    def test_nothing_is_loaded_to_begin_with(self) -> None:
        service = _service()

        assert service.loaded_book() is None
        assert service.loaded_book_id() is None

    def test_forgetting_a_book_purges_its_traces_and_returns_its_id(self) -> None:
        cache = FakeCacheRepo()
        bookmarks = FakeBookmarkService()
        preferences = FakePreferencesRepo()
        service = _service(
            cache_repo=cache,
            bookmark_service=bookmarks,
            preferences_repo=preferences,
        )
        book = _book()
        service.adopt_book(book, _SOURCE)

        assert service.forget_current_book() == book.id
        assert bookmarks.deleted == [book.id]
        assert cache.purged
        assert preferences.cleared == 1
        assert service.loaded_book() is None

    def test_forgetting_nothing_reports_nothing(self) -> None:
        service = _service()

        assert service.forget_current_book() is None


class TestPosition:
    def test_the_position_follows_the_playback_chunk(self) -> None:
        service = _service()
        service._chunks = make_chunks("One. ", "Two. ")
        service._set_state(make_state(playback_chunk_id=1, audible_start=7))

        assert service.current_position() == (1, 7)

    def test_a_char_offset_resolves_to_a_playback_index(self) -> None:
        service = _service()
        chunks = make_chunks("One. ", "Two. ", "Three.")

        resolved = service._resolve_playback_index_for_char_offset(
            char_offset=len("One. ") + 1, chunks=chunks
        )

        assert resolved == 1


class TestResumePersistence:
    def _played(self) -> NarrationService:
        bookmarks = FakeBookmarkService()
        service = _service(bookmark_service=bookmarks)
        service.adopt_book(_book(), _SOURCE)
        service._chunks = make_chunks("One. ", "Two. ")
        service._set_state(make_state(playback_chunk_id=0, audible_start=3))
        return service

    def test_the_position_is_written_through_the_bookmark_service(self) -> None:
        service = self._played()

        service._maybe_save_resume_position()

        assert service.bookmark_service.saved[-1]["char_offset"] == 3

    def test_leaving_the_application_saves_the_position(self) -> None:
        service = self._played()

        service.on_app_exit()

        assert service.bookmark_service.saved[-1]["char_offset"] == 3


class TestTransportControls:
    def test_a_stop_after_the_current_chunk_is_recorded(self) -> None:
        service = _service()

        service.request_stop_after_current_chunk()

        assert service._stop_after_current_chunk.is_set()

    def test_resuming_clears_the_pause_and_returns_to_playing(self) -> None:
        streamer = FakeAudioStreamer()
        service = _service(audio_streamer=streamer)
        service.pause()

        service.resume()

        assert service.state.status is NarrationStatus.PLAYING
        assert not service._pause_event.is_set()
        assert streamer.events[-1] == "resume"


class TestWarmupAndPresynthesis:
    def test_the_startup_warmup_synthesises_once_and_returns_to_idle(self) -> None:
        engine = FakeEngine()
        service = _service(tts_engine=engine)
        seen: list[NarrationStatus] = []
        service.add_listener(lambda state: seen.append(state.status))

        service.startup_warmup(_VOICE)

        assert seen == [NarrationStatus.SYNTHESIZING, NarrationStatus.IDLE]
        assert [call["text"] for call in engine.synthesized] == ["."]

    def _loaded(self, engine: FakeEngine) -> NarrationService:
        navigation = FakeNavigationChunkService(
            chunks=make_chunks("One. ", "Two. ", "Three.")
        )
        service = _service(tts_engine=engine, navigation_chunk_service=navigation)
        service.adopt_book(_book(), _SOURCE)
        # Loading a book stops playback, which leaves the stop event set, and
        # pre-synthesis abandons its first chunk while that event is set. See
        # TECH_DEBT.md: pre-synthesis after a load does nothing until it is
        # cleared, so these tests clear it to reach the work itself.
        service._stop_event.clear()
        return service

    def test_presynthesis_caches_the_first_chunks_only(self) -> None:
        engine = FakeEngine()
        service = self._loaded(engine)

        service.presynthesize_start(_VOICE, cancel_event=threading.Event(), n_chunks=2)

        assert len(engine.synthesized) == 2
        assert all(call["text"] for call in engine.synthesized)

    def test_presynthesis_stops_when_it_is_cancelled(self) -> None:
        engine = FakeEngine()
        service = self._loaded(engine)
        cancelled = threading.Event()
        cancelled.set()

        service.presynthesize_start(_VOICE, cancel_event=cancelled, n_chunks=2)

        assert engine.synthesized == []
