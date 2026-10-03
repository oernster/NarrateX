"""Opening a book settles its bookmark record (audit round 3, N-1 and N-2).

The id scheme changed from filename-plus-opening to the whole text, so a
reader's existing record sits under the book's legacy id until the book is
next opened. Opening it carries that record over; a record found damaged
is kept aside and named in the line the reader reads.
"""

from __future__ import annotations

from pathlib import Path

from tests.application.narration_fakes import (
    FakeBook,
    FakeBookmarkService,
    FakeBookRepo,
    FakeNarrationService,
)
from voice_reader.application.services.bookmark_service import BookmarkService
from voice_reader.application.services.narration.book_loading import (
    adopt_book,
    load_book,
)
from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition

SOURCE = Path("books") / "a-book.txt"


class InMemoryBookmarkRepository:
    """Records held by id, with a set of ids whose file is damaged."""

    def __init__(self) -> None:
        self.records: dict[str, str] = {}
        self.damaged: set[str] = set()
        self.calls: list[str] = []

    def carry_over(self, *, from_id: str, to_id: str) -> bool:
        self.calls.append(f"carry {from_id}->{to_id}")
        if to_id in self.records or from_id not in self.records:
            return False
        self.records[to_id] = self.records.pop(from_id)
        return True

    def keep_aside_if_damaged(self, *, book_id: str) -> Path | None:
        self.calls.append(f"check {book_id}")
        if book_id not in self.damaged:
            return None
        return Path(f"{book_id}.json.damaged")

    # The rest of the port, unused here.
    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]:
        return []

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None:
        return None


class TestSettlingTheRecord:
    def test_a_legacy_record_is_carried_then_checked(self) -> None:
        repo = InMemoryBookmarkRepository()
        repo.records["old"] = "three bookmarks"

        kept = BookmarkService(repo=repo).settle_book_records(
            book_id="new", legacy_ids=("old",)
        )

        assert kept is None
        assert repo.records == {"new": "three bookmarks"}
        assert repo.calls == ["carry old->new", "check new"]

    def test_a_damaged_record_is_named(self) -> None:
        repo = InMemoryBookmarkRepository()
        repo.damaged.add("new")

        kept = BookmarkService(repo=repo).settle_book_records(
            book_id="new", legacy_ids=()
        )

        assert kept == Path("new.json.damaged")


class TestLoading:
    def test_loading_settles_the_record_under_both_ids(self) -> None:
        book = FakeBook(normalized_text="Text.", id="new", legacy_ids=("old",))
        service = FakeNarrationService(book_repo=FakeBookRepo(book))

        load_book(service, SOURCE)

        assert service.bookmark_service.settled == ("new", ("old",))
        assert service.state.message == "Loaded 'A Book'"

    def test_a_kept_aside_record_is_named_where_the_reader_looks(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.kept_aside = Path("bookmarks") / "new.json.damaged"
        book = FakeBook(normalized_text="Text.", id="new")
        service = FakeNarrationService(bookmark_service=bookmarks)

        adopt_book(service, book, SOURCE)

        assert service.state.message == (
            "Loaded 'A Book'. Its bookmark file was damaged and is kept as "
            "new.json.damaged"
        )

    def test_a_failure_settling_does_not_prevent_the_load(self) -> None:
        bookmarks = FakeBookmarkService()
        bookmarks.fail_settle = True
        service = FakeNarrationService(bookmark_service=bookmarks)

        adopt_book(service, FakeBook(normalized_text="Text."), SOURCE)

        assert service.state.message == "Loaded 'A Book'"

    def test_no_bookmark_service_is_no_fault(self) -> None:
        service = FakeNarrationService(bookmark_service=None)

        adopt_book(service, FakeBook(normalized_text="Text."), SOURCE)

        assert service.state.message == "Loaded 'A Book'"
