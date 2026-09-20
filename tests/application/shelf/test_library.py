"""The shelf a reader looks at, driven with no window open."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from voice_reader.application.services.shelf import ShelfLibrary
from voice_reader.domain.shelf.identity import ShelfEntry
from voice_reader.domain.shelf.progress import ReadingState
from voice_reader.domain.shelf.query import Order, ShelfQuery

from tests.application.shelf.shelf_fakes import (
    FakeBookmarks,
    FakeIndex,
    key,
    resume_at,
)

ROOT = Path("H:/Books")
INSIDE = Path("H:/Books/FIXED")
OTHER = Path("D:/Other")


def entry(
    path: str,
    title: str,
    author: str,
    *,
    subjects: tuple[str, ...] = (),
    book_id: str | None = None,
    total_chars: int | None = None,
) -> ShelfEntry:
    return ShelfEntry(
        key=key(path),
        title=title,
        author=author,
        subjects=subjects,
        book_id=book_id,
        total_chars=total_chars,
    )


SHINING = entry("H:/Books/a.mobi", "The Shining", "Stephen King", subjects=("Horror",))
RAMA = entry("H:/Books/b.azw3", "Rama", "Arthur C. Clarke", subjects=("Space Opera",))


def library(**kwargs) -> tuple[ShelfLibrary, FakeIndex, FakeBookmarks]:
    index = FakeIndex(**kwargs)
    bookmarks = FakeBookmarks()
    return ShelfLibrary(index=index, bookmarks=bookmarks), index, bookmarks


# Roots ---------------------------------------------------------------------


def test_a_folder_becomes_a_root() -> None:
    shelf, index, _ = library()
    outcome = shelf.add_root(ROOT)
    assert outcome.added
    assert index.load_roots() == (ROOT,)


def test_a_folder_inside_an_existing_root_is_refused_with_a_reason() -> None:
    shelf, index, _ = library(roots=(ROOT,))
    outcome = shelf.add_root(INSIDE)
    assert not outcome.added
    assert outcome.covered_by == ROOT
    assert index.load_roots() == (ROOT,)


def test_a_folder_that_swallows_a_root_replaces_it() -> None:
    shelf, index, _ = library(roots=(INSIDE,))
    outcome = shelf.add_root(ROOT)
    assert outcome.added
    assert outcome.replaced == (INSIDE,)
    assert index.load_roots() == (ROOT,)


def test_removing_a_root_drops_the_entries_found_only_beneath_it() -> None:
    elsewhere = entry("D:/Other/c.epub", "Other", "Someone Else")
    shelf, index, _ = library(roots=(ROOT, OTHER), entries=(SHINING, elsewhere))
    remaining = shelf.remove_root(ROOT)
    assert remaining == (OTHER,)
    assert [e.title for e in index.load_entries()] == ["Other"]


# The shelf -----------------------------------------------------------------


def test_the_shelf_folds_entries_into_works() -> None:
    twin = entry("H:/Books/c.mobi", "The Shining", "Stephen King")
    shelf, _, _ = library(entries=(SHINING, twin))
    assert len(shelf.works()) == 1


def test_a_filter_narrows_the_shelf() -> None:
    shelf, _, _ = library(entries=(SHINING, RAMA))
    shown = shelf.view(ShelfQuery(genres=frozenset({"Horror"})))
    assert [work.title for work in shown] == ["The Shining"]


def test_a_search_narrows_the_shelf() -> None:
    shelf, _, _ = library(entries=(SHINING, RAMA))
    assert [w.title for w in shelf.view(ShelfQuery(text="clarke"))] == ["Rama"]


def test_the_filter_dialog_is_told_what_each_genre_holds() -> None:
    shelf, _, _ = library(entries=(SHINING, RAMA))
    counts = shelf.genre_counts()
    assert counts["Horror"] == 1
    assert counts["Science Fiction"] == 1


def test_works_stating_no_genre_are_counted_for_their_own_choice() -> None:
    plain = entry("H:/Books/d.mobi", "Untagged", "Zoe Zeta")
    shelf, _, _ = library(entries=(SHINING, plain))
    assert shelf.ungenred_count() == 1


def test_the_unmatched_report_names_what_the_catalogue_missed() -> None:
    odd = entry("H:/Books/e.mobi", "Odd", "Zoe Zeta", subjects=("Azizex666",))
    shelf, _, _ = library(entries=(odd,))
    assert shelf.unmatched_subjects() == ("Azizex666",)


def test_possible_duplicates_are_reported() -> None:
    longer = entry("H:/Books/f.mobi", "The Shining Complete", "Stephen King")
    shelf, _, _ = library(entries=(SHINING, longer))
    assert len(shelf.duplicates()) == 1


# One work ------------------------------------------------------------------


def test_a_work_never_opened_shows_no_progress() -> None:
    shelf, _, _ = library(entries=(SHINING,))
    assert shelf.progress_of(shelf.works()[0]).state is ReadingState.UNREAD


def test_a_work_opened_but_never_resumed_shows_no_progress() -> None:
    opened = entry(
        "H:/Books/a.mobi", "The Shining", "Stephen King", book_id="abc", total_chars=100
    )
    shelf, _, _ = library(entries=(opened,))
    assert shelf.progress_of(shelf.works()[0]).state is ReadingState.UNREAD


def test_a_work_with_no_length_yet_shows_no_progress() -> None:
    opened = entry("H:/Books/a.mobi", "The Shining", "Stephen King", book_id="abc")
    index = FakeIndex(entries=(opened,))
    bookmarks = FakeBookmarks({"abc": resume_at(50)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    assert shelf.progress_of(shelf.works()[0]).state is ReadingState.UNREAD


def test_a_work_half_read_reads_as_reading() -> None:
    opened = entry(
        "H:/Books/a.mobi", "The Shining", "Stephen King", book_id="abc", total_chars=100
    )
    index = FakeIndex(entries=(opened,))
    bookmarks = FakeBookmarks({"abc": resume_at(50)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    reading = shelf.progress_of(shelf.works()[0])
    assert reading.state is ReadingState.READING
    assert reading.percent == 50


def test_a_work_listened_to_the_end_reads_as_finished() -> None:
    opened = entry(
        "H:/Books/a.mobi", "The Shining", "Stephen King", book_id="abc", total_chars=100
    )
    index = FakeIndex(entries=(opened,))
    bookmarks = FakeBookmarks({"abc": resume_at(100)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    assert shelf.progress_of(shelf.works()[0]).state is ReadingState.FINISHED


def test_the_work_opens_its_cheapest_format() -> None:
    kindle = entry("H:/Books/a.mobi", "The Shining", "Stephen King")
    native = entry("H:/Books/a.epub", "The Shining", "Stephen King")
    shelf, _, _ = library(entries=(kindle, native))
    assert shelf.path_to_open(shelf.works()[0]) == Path("H:/Books/a.epub")


def test_opening_a_work_records_its_reading_identity() -> None:
    shelf, index, _ = library(entries=(SHINING,))
    shelf.record_reading_identity(shelf.works()[0], book_id="abc", total_chars=2000)
    entry_now = index.load_entries()[0]
    assert (entry_now.book_id, entry_now.total_chars) == ("abc", 2000)


def test_only_the_files_of_that_work_gain_the_identity() -> None:
    shelf, index, _ = library(entries=(SHINING, RAMA))
    shining = next(w for w in shelf.works() if w.title == "The Shining")
    shelf.record_reading_identity(shining, book_id="abc", total_chars=10)
    rama = next(e for e in index.load_entries() if e.title == "Rama")
    assert rama.book_id is None


def test_ordering_by_most_recently_read_uses_the_resume_times() -> None:
    first = entry(
        "H:/Books/a.mobi", "Aaa", "Aaa Author", book_id="one", total_chars=100
    )
    second = entry(
        "H:/Books/b.mobi", "Bbb", "Bbb Author", book_id="two", total_chars=100
    )
    index = FakeIndex(entries=(first, second))
    bookmarks = FakeBookmarks(
        {
            "one": resume_at(10, when=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            "two": resume_at(10, when=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        }
    )
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    shown = shelf.view(ShelfQuery(order=Order.RECENTLY_READ))
    assert [work.title for work in shown] == ["Bbb", "Aaa"]


def test_a_work_never_resumed_sorts_after_the_ones_that_were() -> None:
    read = entry("H:/Books/a.mobi", "Zzz", "Zzz Author", book_id="one", total_chars=100)
    unread = entry("H:/Books/b.mobi", "Aaa", "Aaa Author")
    index = FakeIndex(entries=(read, unread))
    bookmarks = FakeBookmarks({"one": resume_at(10)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    shown = shelf.view(ShelfQuery(order=Order.RECENTLY_READ))
    assert [work.title for work in shown] == ["Zzz", "Aaa"]


def test_a_work_opened_but_never_resumed_sorts_with_the_unread() -> None:
    """A book id with no resume position is a book opened and put down."""

    opened = entry(
        "H:/Books/a.mobi", "Zzz", "Zzz Author", book_id="one", total_chars=100
    )
    resumed = entry(
        "H:/Books/b.mobi", "Aaa", "Aaa Author", book_id="two", total_chars=100
    )
    index = FakeIndex(entries=(opened, resumed))
    bookmarks = FakeBookmarks({"two": resume_at(10)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)
    shown = shelf.view(ShelfQuery(order=Order.RECENTLY_READ))
    assert [work.title for work in shown] == ["Aaa", "Zzz"]


# What the reader states ----------------------------------------------------


def test_a_reader_can_file_a_work_under_a_genre() -> None:
    shelf, _, _ = library(entries=(SHINING,))
    shelf.state_genres(shelf.works(), ("Space Opera",))
    filed = shelf.works()[0]
    assert filed.carries("Space Opera")
    assert not filed.carries("Horror")


def test_a_statement_survives_a_rescan_of_the_same_book() -> None:
    shelf, index, _ = library(entries=(SHINING,))
    shelf.state_genres(shelf.works(), ("Fantasy",))
    index.save_entries((entry("H:/Books/a.mobi", "The Shining", "Stephen King"),))
    assert shelf.works()[0].carries("Fantasy")


def test_several_works_can_be_filed_at_once() -> None:
    shelf, _, _ = library(entries=(SHINING, RAMA))
    shelf.state_genres(shelf.works(), ("Horror",))
    assert all(work.carries("Horror") for work in shelf.works())


def test_stating_no_genre_clears_the_statement() -> None:
    shelf, _, _ = library(entries=(SHINING,))
    shelf.state_genres(shelf.works(), ("Fantasy",))
    shelf.state_genres(shelf.works(), ())
    assert shelf.works()[0].carries("Horror")


# Forgetting ----------------------------------------------------------------


def test_forgetting_a_work_keeps_its_tile_and_its_file() -> None:
    opened = entry(
        "H:/Books/a.mobi", "The Shining", "Stephen King", book_id="abc", total_chars=100
    )
    index = FakeIndex(entries=(opened,))
    bookmarks = FakeBookmarks({"abc": resume_at(50)})
    shelf = ShelfLibrary(index=index, bookmarks=bookmarks)

    shelf.forget(shelf.works()[0])

    still_there = index.load_entries()[0]
    assert still_there.title == "The Shining"
    assert still_there.book_id is None
    assert still_there.total_chars is None
    assert bookmarks.deleted == ["abc"]
    assert shelf.progress_of(shelf.works()[0]).state is ReadingState.UNREAD


def test_forgetting_a_work_never_opened_touches_no_bookmarks() -> None:
    shelf, index, bookmarks = library(entries=(SHINING,))
    shelf.forget(shelf.works()[0])
    assert bookmarks.deleted == []
    assert len(index.load_entries()) == 1


def test_forgetting_one_work_leaves_the_others_alone() -> None:
    opened = entry(
        "H:/Books/b.azw3", "Rama", "Arthur C. Clarke", book_id="two", total_chars=10
    )
    shelf, index, _ = library(entries=(SHINING, opened))
    shining = next(w for w in shelf.works() if w.title == "The Shining")
    shelf.forget(shining)
    rama = next(e for e in index.load_entries() if e.title == "Rama")
    assert rama.book_id == "two"
