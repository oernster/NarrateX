"""The shelf's composition, proved over real files rather than over fakes.

`build_shelf` is the one place the four shelf ports meet their real
implementations, so the thing worth asserting is not that it returns three
objects: it is that the objects it returns work against a disk. Every test here
drives the wiring it built over a planted library and reads the result.

The bookmark repository is the one hand-written stand-in, because progress is
not what is under test and the real one wants a directory of its own.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from voice_reader import bootstrap
from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition

_SHELF_WIRING = (
    "FileSystemWalker",
    "FileThumbnailStore",
    "QtThumbnailMaker",
    "ShelfCoverReader",
    "ShelfCovers",
    "ShelfLibrary",
    "ShelfMetadataReader",
    "ShelfScanner",
    "SqliteShelfIndex",
)


class _FakeBookmarks:
    """Enough of BookmarkRepository for the shelf to read progress from."""

    def __init__(self, resume: dict[str, ResumePosition] | None = None) -> None:
        self._resume = resume or {}

    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]:
        return []

    def add_bookmark(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> Bookmark:
        raise AssertionError("the shelf never adds a bookmark")

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        raise AssertionError("the shelf never deletes a bookmark")

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None:
        return self._resume.get(book_id)

    def save_resume_position(
        self, *, book_id: str, char_offset: int, chunk_index: int
    ) -> None:
        raise AssertionError("the shelf never writes a resume position")

    def delete_book(self, *, book_id: str) -> None:
        self._resume.pop(book_id, None)


def _resolver():
    """The wiring names resolved through the table the entrypoint uses.

    Reading the real table rather than a local mapping means a table entry
    naming the wrong module or attribute fails here, which is the only place
    short of a launch where it can be caught.
    """

    table = bootstrap._APP_WIRING_IMPORTS
    loaded = {
        name: getattr(importlib.import_module(table[name][0]), table[name][1])
        for name in _SHELF_WIRING
    }
    return loaded.__getitem__


def _built(tmp_path: Path, bookmarks: object | None = None) -> bootstrap.Shelf:
    return bootstrap.build_shelf(
        _resolver(),
        index_dir=tmp_path / "data" / "shelf",
        thumbnails_dir=tmp_path / "cache" / "shelf_thumbnails",
        bookmark_repo=bookmarks or _FakeBookmarks(),
    )


def test_the_scanner_and_the_library_share_one_index(tmp_path: Path) -> None:
    """Two indexes would let a scan and the shelf disagree about the shelf."""

    shelf = _built(tmp_path)

    assert shelf.scanner.index is shelf.library.index


def test_the_index_and_the_thumbnails_land_where_they_were_told(
    tmp_path: Path,
) -> None:
    shelf = _built(tmp_path)

    assert shelf.scanner.index.directory == tmp_path / "data" / "shelf"
    assert shelf.thumbnails.directory == tmp_path / "cache" / "shelf_thumbnails"


def test_the_library_reads_progress_from_the_repository_it_was_given(
    tmp_path: Path,
) -> None:
    bookmarks = _FakeBookmarks()
    shelf = _built(tmp_path, bookmarks=bookmarks)

    assert shelf.library.bookmarks is bookmarks


def test_a_scan_through_the_wiring_finds_a_planted_book(tmp_path: Path) -> None:
    library_root = tmp_path / "Books"
    library_root.mkdir()
    (library_root / "Dune - Frank Herbert.epub").write_bytes(b"not a real epub")
    shelf = _built(tmp_path)
    shelf.library.add_root(library_root)

    report = shelf.scanner.scan()

    assert report.found == 1
    assert report.added == 1
    assert not report.unreachable_roots
    works = shelf.library.works()
    assert [work.title for work in works] == ["Dune"]


def test_nothing_is_written_inside_the_shelf_root(tmp_path: Path) -> None:
    """DATA-BS-003: the index lives in the application's storage, never in a root."""

    library_root = tmp_path / "Books"
    library_root.mkdir()
    (library_root / "Dune - Frank Herbert.epub").write_bytes(b"not a real epub")
    before = sorted(path.name for path in library_root.iterdir())
    shelf = _built(tmp_path)
    shelf.library.add_root(library_root)

    shelf.scanner.scan()

    assert sorted(path.name for path in library_root.iterdir()) == before
    assert (tmp_path / "data" / "shelf" / "shelf.sqlite3").is_file()


def test_a_rescan_rereads_nothing_that_has_not_changed(tmp_path: Path) -> None:
    library_root = tmp_path / "Books"
    library_root.mkdir()
    (library_root / "Dune - Frank Herbert.epub").write_bytes(b"not a real epub")
    shelf = _built(tmp_path)
    shelf.library.add_root(library_root)
    shelf.scanner.scan()

    again = shelf.scanner.scan()

    assert again.kept == 1
    assert again.added == 0
    assert again.rereads == 0
