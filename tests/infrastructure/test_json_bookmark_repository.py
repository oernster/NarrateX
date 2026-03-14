from __future__ import annotations

import json
from pathlib import Path

from voice_reader.infrastructure.bookmarks.json_bookmark_repository import (
    JSONBookmarkRepository,
)


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    assert repo.list_bookmarks(book_id="b1") == []
    assert repo.load_resume_position(book_id="b1") is None


def test_add_bookmark_creates_file_and_allocates_monotonic_ids(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)

    b1 = repo.add_bookmark(book_id="b1", char_offset=10, chunk_index=1)
    assert b1.bookmark_id == 1
    assert b1.name == "Bookmark 1"

    b2 = repo.add_bookmark(book_id="b1", char_offset=20, chunk_index=2)
    assert b2.bookmark_id == 2
    assert b2.name == "Bookmark 2"

    listed = repo.list_bookmarks(book_id="b1")
    assert [b.bookmark_id for b in listed] == [1, 2]

    # Delete does not reuse IDs.
    repo.delete_bookmark(book_id="b1", bookmark_id=2)
    b3 = repo.add_bookmark(book_id="b1", char_offset=30, chunk_index=3)
    assert b3.bookmark_id == 3


def test_delete_bookmark_removes_only_target(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    repo.add_bookmark(book_id="b1", char_offset=10, chunk_index=1)
    repo.add_bookmark(book_id="b1", char_offset=20, chunk_index=2)
    repo.add_bookmark(book_id="b1", char_offset=30, chunk_index=3)

    repo.delete_bookmark(book_id="b1", bookmark_id=2)
    ids = [b.bookmark_id for b in repo.list_bookmarks(book_id="b1")]
    assert ids == [1, 3]


def test_resume_persistence_roundtrip(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    assert repo.load_resume_position(book_id="b1") is None

    repo.save_resume_position(book_id="b1", char_offset=41231, chunk_index=12)
    rp = repo.load_resume_position(book_id="b1")
    assert rp is not None
    assert rp.char_offset == 41231
    assert rp.chunk_index == 12


def test_tolerates_empty_or_missing_keys(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    path = tmp_path / "b1.json"
    path.write_text("{}", encoding="utf-8")
    assert repo.list_bookmarks(book_id="b1") == []
    assert repo.load_resume_position(book_id="b1") is None

    # And it can write over it.
    repo.add_bookmark(book_id="b1", char_offset=1, chunk_index=0)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "bookmarks" in doc
    assert "next_bookmark_id" in doc
