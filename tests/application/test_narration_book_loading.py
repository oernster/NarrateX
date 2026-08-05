"""Loading, adopting and forgetting a book.

`load_book` parses; `adopt_book` takes a book the load worker already parsed and
does everything else `load_book` does around the parse. `forget_current_book`
tears down every derived artefact and never touches the file on disk.
"""

from __future__ import annotations

from pathlib import Path

from tests.application.narration_fakes import (
    FakeBook,
    FakeBookmarkService,
    FakeBookRepo,
    FakeCacheRepo,
    FakeNarrationService,
    FakePreferencesRepo,
    make_chunks,
    make_state,
)
from voice_reader.application.dto.narration_state import NarrationStatus
from voice_reader.application.services.narration.book_loading import (
    adopt_book,
    forget_current_book,
    load_book,
)
from voice_reader.domain.document import plain_text

SOURCE = Path("books") / "a-book.epub"
TEXT = "Chapter 1\n\nSome prose here.\n"


def _book() -> FakeBook:
    return FakeBook(
        normalized_text=TEXT,
        document_model=plain_text.build_document(source=TEXT),
    )


class TestLoading:
    def test_a_loaded_book_is_adopted_and_announced(self) -> None:
        book = _book()
        service = FakeNarrationService(book_repo=FakeBookRepo(book))

        assert load_book(service, SOURCE) is book
        assert service._book is book
        assert service.book_repo.loaded == [SOURCE]
        assert service.state.status is NarrationStatus.IDLE
        assert service.state.message == "Loaded 'A Book'"
        assert service.preferences_repo.saved_paths == [SOURCE]

    def test_loading_announces_itself_before_the_parse(self) -> None:
        service = FakeNarrationService(book_repo=FakeBookRepo(_book()))

        load_book(service, SOURCE)

        assert service.states[0].status is NarrationStatus.LOADING
        assert service.states[0].message == "Loading a-book.epub..."

    def test_loading_stops_whatever_was_playing(self) -> None:
        service = FakeNarrationService(book_repo=FakeBookRepo(_book()))

        load_book(service, SOURCE)

        assert service.stops == [True]

    def test_a_failure_stopping_does_not_prevent_the_load(self) -> None:
        service = FakeNarrationService(book_repo=FakeBookRepo(_book()), fail_stop=True)

        load_book(service, SOURCE)

        assert service.state.status is NarrationStatus.IDLE

    def test_a_failure_recording_the_last_book_is_swallowed(self) -> None:
        service = FakeNarrationService(
            book_repo=FakeBookRepo(_book()),
            preferences_repo=FakePreferencesRepo(fail_save_path=True),
        )

        load_book(service, SOURCE)

        assert service.state.status is NarrationStatus.IDLE

    def test_no_preferences_repository_is_allowed(self) -> None:
        service = FakeNarrationService(
            book_repo=FakeBookRepo(_book()), preferences_repo=None
        )

        load_book(service, SOURCE)

        assert service.state.status is NarrationStatus.IDLE

    def test_adopting_a_parsed_book_skips_the_parse(self) -> None:
        book = _book()
        service = FakeNarrationService()

        assert adopt_book(service, book, SOURCE) is book
        assert service.book_repo.loaded == []
        assert service._book is book
        assert service.state.message == "Loaded 'A Book'"


class TestForgetting:
    def _loaded(self, **kwargs) -> FakeNarrationService:
        kwargs.setdefault("_book", _book())
        kwargs.setdefault("_chunks", make_chunks("one ", "two "))
        kwargs.setdefault("state", make_state(playback_chunk_id=0, audible_start=1))
        return FakeNarrationService(**kwargs)

    def test_forgetting_nothing_reports_nothing(self) -> None:
        assert forget_current_book(FakeNarrationService()) is None

    def test_every_derived_artefact_is_removed(self) -> None:
        service = self._loaded()

        assert forget_current_book(service) == "book-1"
        assert service.stops == [False]
        assert service.cache_repo.purged and service.cache_repo.purged[0] != "book-1"
        assert service.bookmark_service.deleted == ["book-1"]
        assert service.preferences_repo.cleared == 1
        assert service._book is None
        assert service._chunks == []
        assert service._cache_book_id is None
        assert service.state.message == "Removed 'A Book' (the file is kept)"

    def test_the_resume_position_is_not_saved_on_the_way_out(self) -> None:
        service = self._loaded()

        forget_current_book(service)

        assert service.bookmark_service.saved == []

    def test_an_uncomputable_cache_id_skips_the_purge(self) -> None:
        service = self._loaded(cache_repo=FakeCacheRepo(fail_paths=True))
        service._book = None
        service._book = FakeBook(normalized_text=TEXT, document_model=None)

        assert forget_current_book(service) == "book-1"
        assert service.cache_repo.purged == []

    def test_a_failing_purge_is_swallowed(self) -> None:
        service = self._loaded(cache_repo=FakeCacheRepo(fail_purge=True))

        assert forget_current_book(service) == "book-1"
        assert service._book is None

    def test_a_failing_stop_is_swallowed(self) -> None:
        service = self._loaded(fail_stop=True)

        assert forget_current_book(service) == "book-1"

    def test_a_failing_bookmark_delete_is_swallowed(self) -> None:
        service = self._loaded(bookmark_service=FakeBookmarkService(fail_delete=True))

        assert forget_current_book(service) == "book-1"

    def test_a_failing_preference_clear_is_swallowed(self) -> None:
        service = self._loaded(
            preferences_repo=FakePreferencesRepo(fail_clear_path=True)
        )

        assert forget_current_book(service) == "book-1"

    def test_no_bookmark_service_or_preferences_is_allowed(self) -> None:
        service = self._loaded(bookmark_service=None, preferences_repo=None)

        assert forget_current_book(service) == "book-1"
