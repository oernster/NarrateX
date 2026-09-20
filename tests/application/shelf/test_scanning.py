"""Scanning and rescanning: what changes, what is kept and what is never lost."""

from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.shelf import ShelfScanner
from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfEntry

from tests.application.shelf.shelf_fakes import (
    FakeIndex,
    FakeMetadataReader,
    FakeWalker,
    key,
)

ROOT = Path("H:/Books")
FIRST = "H:/Books/The Shining - Stephen King.mobi"
SECOND = "H:/Books/Rama - Arthur C. Clarke.azw3"


def scanner(walker: FakeWalker, metadata: FakeMetadataReader, index: FakeIndex):
    return ShelfScanner(walker=walker, metadata=metadata, index=index)


def test_a_first_scan_records_every_book_it_finds() -> None:
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST), key(SECOND)))})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert report.found == 2
    assert report.added == 2
    assert report.removed == 0
    assert len(index.load_entries()) == 2


def test_the_scan_walks_the_roots_the_index_holds() -> None:
    walker = FakeWalker()
    index = FakeIndex(roots=(ROOT, Path("D:/Other")))
    scanner(walker, FakeMetadataReader(), index).scan()
    assert walker.walked == [ROOT, Path("D:/Other")]


def test_roots_can_be_named_for_one_scan() -> None:
    walker = FakeWalker()
    index = FakeIndex(roots=(ROOT,))
    scanner(walker, FakeMetadataReader(), index).scan(roots=(Path("D:/Other"),))
    assert walker.walked == [Path("D:/Other")]


def test_metadata_outranks_the_filename() -> None:
    stated = {
        Path(FIRST): FileMetadata(
            title="The Shining", author="Stephen Edwin King", subjects=("Horror",)
        )
    }
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST),))})
    index = FakeIndex(roots=(ROOT,))
    scanner(walker, FakeMetadataReader(stated), index).scan()

    entry = index.load_entries()[0]
    assert entry.author == "Stephen Edwin King"
    assert entry.subjects == ("Horror",)


def test_a_file_stating_nothing_falls_back_to_its_name() -> None:
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST),))})
    index = FakeIndex(roots=(ROOT,))
    scanner(walker, FakeMetadataReader(), index).scan()

    entry = index.load_entries()[0]
    assert (entry.title, entry.author) == ("The Shining", "Stephen King")


def test_a_file_that_cannot_be_read_still_reaches_the_shelf() -> None:
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST),))})
    metadata = FakeMetadataReader(unreadable={Path(FIRST)})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, metadata, index).scan()

    assert report.added == 1
    assert index.load_entries()[0].title == "The Shining"


def test_an_unchanged_file_is_never_read_again() -> None:
    known = ShelfEntry(key=key(FIRST), title="The Shining", author="Stephen King")
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST),))})
    metadata = FakeMetadataReader()
    index = FakeIndex(roots=(ROOT,), entries=(known,))
    report = scanner(walker, metadata, index).scan()

    assert report.kept == 1
    assert report.added == 0
    assert metadata.read_paths == []


def test_a_changed_file_is_read_again() -> None:
    known = ShelfEntry(key=key(FIRST), title="Old", author="Stephen King")
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST, size=999),))})
    metadata = FakeMetadataReader()
    index = FakeIndex(roots=(ROOT,), entries=(known,))
    report = scanner(walker, metadata, index).scan()

    assert report.rereads == 1
    assert metadata.read_paths == [Path(FIRST)]


def test_a_changed_file_keeps_the_identity_the_reader_paid_for() -> None:
    known = ShelfEntry(
        key=key(FIRST),
        title="The Shining",
        author="Stephen King",
        book_id="abc",
        total_chars=1000,
    )
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST, modified=99),))})
    index = FakeIndex(roots=(ROOT,), entries=(known,))
    scanner(walker, FakeMetadataReader(), index).scan()

    entry = index.load_entries()[0]
    assert (entry.book_id, entry.total_chars) == ("abc", 1000)


def test_a_deleted_file_leaves_the_index() -> None:
    known = ShelfEntry(key=key(FIRST), title="The Shining", author="Stephen King")
    walker = FakeWalker({ROOT: WalkResult()})
    index = FakeIndex(roots=(ROOT,), entries=(known,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert report.removed == 1
    assert index.load_entries() == ()


def test_an_unreachable_root_removes_nothing() -> None:
    known = ShelfEntry(key=key(FIRST), title="The Shining", author="Stephen King")
    walker = FakeWalker({ROOT: WalkResult(root_reachable=False)})
    index = FakeIndex(roots=(ROOT,), entries=(known,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert report.unreachable_roots == (ROOT,)
    assert report.removed == 0
    assert index.load_entries() == (known,)


def test_an_unreadable_folder_is_reported_and_the_scan_finishes() -> None:
    locked = Path("H:/Books/locked")
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST),), unreadable=(locked,))})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert report.unreadable == (locked,)
    assert report.added == 1


def test_a_root_holding_nothing_readable_says_so() -> None:
    walker = FakeWalker({ROOT: WalkResult()})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert report.found_nothing
    assert report.total == 0


def test_an_unreachable_root_is_not_an_empty_one() -> None:
    walker = FakeWalker({ROOT: WalkResult(root_reachable=False)})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert not report.found_nothing


def test_the_same_file_found_twice_becomes_one_entry() -> None:
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST), key(FIRST)))})
    index = FakeIndex(roots=(ROOT,))
    report = scanner(walker, FakeMetadataReader(), index).scan()

    assert len(index.load_entries()) == 1
    assert report.added == 1


def test_the_shelf_is_told_of_each_entry_as_it_is_settled() -> None:
    walker = FakeWalker({ROOT: WalkResult(keys=(key(FIRST), key(SECOND)))})
    index = FakeIndex(roots=(ROOT,))
    seen: list[str] = []
    scanner(walker, FakeMetadataReader(), index).scan(
        on_entry=lambda e: seen.append(e.title)
    )

    assert seen == ["The Shining", "Rama"]


def test_the_corpus_rule_runs_over_what_the_scan_found() -> None:
    stems = [
        "H:/Books/American Gods - Neil Gaiman.mobi",
        "H:/Books/Anansi Boys - Neil Gaiman.mobi",
        "H:/Books/Neverwhere - Neil Gaiman.mobi",
        "H:/Books/Neil Gaiman - A Study in Emerald.mobi",
    ]
    walker = FakeWalker({ROOT: WalkResult(keys=tuple(key(s) for s in stems))})
    index = FakeIndex(roots=(ROOT,))
    scanner(walker, FakeMetadataReader(), index).scan()

    swapped = index.load_entries()[-1]
    assert (swapped.title, swapped.author) == ("A Study in Emerald", "Neil Gaiman")
