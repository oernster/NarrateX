"""A genre the reader stated survives a rescan that retitles the book (N-7).

Stated genres are keyed by the work's token, its folded author and title. A
corrected sidecar title changed the token, so the filing silently left the tile
and stayed orphaned in the index. The scan now carries a filing to the token
the same file folds to after the re-read.
"""

from __future__ import annotations

from pathlib import Path

from tests.application.shelf.shelf_fakes import (
    FakeIndex,
    FakeMetadataReader,
    FakeWalker,
    key,
)
from voice_reader.application.services.shelf.scanning import ShelfScanner
from voice_reader.domain.shelf import works
from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfEntry

ROOT = Path("/books")
DUNE = "/books/Dune/Dune.epub"
OTHER = "/books/Dune/Dune.mobi"
FILED = ("Science Fiction",)


def _entry(path: str, title: str, *, modified: int = 1) -> ShelfEntry:
    return ShelfEntry(
        key=key(path, modified=modified), title=title, author="Frank Herbert"
    )


def _token(*entries: ShelfEntry) -> str:
    (work,) = works.gather(entries)
    return work.token


def _rescan(index: FakeIndex, *paths: str, title: str) -> None:
    keys = tuple(key(path, modified=2) for path in paths)
    metadata = FakeMetadataReader(
        {k.path: FileMetadata(title=title, author="Frank Herbert") for k in keys}
    )
    walker = FakeWalker({ROOT: WalkResult(keys=keys)})
    ShelfScanner(walker=walker, metadata=metadata, index=index).scan(roots=(ROOT,))


def test_a_corrected_title_keeps_the_filing() -> None:
    before = _entry(DUNE, "Dune")
    index = FakeIndex(entries=(before,), stated={_token(before): FILED})

    _rescan(index, DUNE, title="Dune: Deluxe Edition")

    after = _entry(DUNE, "Dune: Deluxe Edition")
    assert index.load_stated_genres() == {_token(after): FILED}


def test_a_filing_the_new_title_already_has_is_not_overwritten() -> None:
    before = _entry(DUNE, "Dune")
    after = _entry(DUNE, "Dune: Deluxe Edition")
    index = FakeIndex(
        entries=(before,),
        stated={_token(before): FILED, _token(after): ("Classics",)},
    )

    _rescan(index, DUNE, title="Dune: Deluxe Edition")

    assert index.load_stated_genres()[_token(after)] == ("Classics",)


def test_the_old_filing_stays_while_another_file_still_holds_it() -> None:
    epub, mobi = _entry(DUNE, "Dune"), _entry(OTHER, "Dune")
    index = FakeIndex(entries=(epub, mobi), stated={_token(epub): FILED})
    walker_keys = (key(DUNE, modified=2), key(OTHER))
    metadata = FakeMetadataReader(
        {
            walker_keys[0].path: FileMetadata(
                title="Dune: Deluxe Edition", author="Frank Herbert"
            )
        }
    )
    ShelfScanner(
        walker=FakeWalker({ROOT: WalkResult(keys=walker_keys)}),
        metadata=metadata,
        index=index,
    ).scan(roots=(ROOT,))

    retitled = _entry(DUNE, "Dune: Deluxe Edition")
    assert index.load_stated_genres() == {
        _token(epub): FILED,
        _token(retitled): FILED,
    }


def test_a_scan_that_changes_no_token_leaves_the_filings_alone() -> None:
    before = _entry(DUNE, "Dune")
    index = FakeIndex(entries=(before,), stated={_token(before): FILED})

    _rescan(index, DUNE, title="Dune")

    assert index.load_stated_genres() == {_token(before): FILED}
