"""A damaged bookmark file is kept aside, never saved over (audit round 3, N-2).

Pause, stop, exit and seek all save the resume position on their own. Before
this, a file that failed to parse read as empty and that empty document was
written straight over it, so one stray byte cost every bookmark the reader had.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voice_reader.infrastructure.bookmarks.json_bookmark_repository import (
    JSONBookmarkRepository,
)

BOOK = "book-1"


def _store(tmp_path: Path) -> JSONBookmarkRepository:
    return JSONBookmarkRepository(bookmarks_dir=tmp_path)


def _with_three_bookmarks(tmp_path: Path) -> JSONBookmarkRepository:
    store = _store(tmp_path)
    for offset in (10, 20, 30):
        store.add_bookmark(book_id=BOOK, char_offset=offset, chunk_index=offset)
    return store


def _damage(path: Path) -> bytes:
    path.write_bytes(path.read_bytes() + b"\xff")
    return path.read_bytes()


def test_an_automatic_save_keeps_a_damaged_file_aside(tmp_path: Path) -> None:
    store = _with_three_bookmarks(tmp_path)
    damaged = _damage(tmp_path / f"{BOOK}.json")

    store.save_resume_position(book_id=BOOK, char_offset=5, chunk_index=0)

    kept = tmp_path / f"{BOOK}.json.damaged"
    assert kept.read_bytes() == damaged
    assert store.load_resume_position(book_id=BOOK) is not None


def test_a_manual_bookmark_keeps_a_damaged_file_aside(tmp_path: Path) -> None:
    store = _with_three_bookmarks(tmp_path)
    damaged = _damage(tmp_path / f"{BOOK}.json")

    store.add_bookmark(book_id=BOOK, char_offset=40, chunk_index=4)

    assert (tmp_path / f"{BOOK}.json.damaged").read_bytes() == damaged


def test_an_earlier_kept_copy_is_never_overwritten(tmp_path: Path) -> None:
    store = _with_three_bookmarks(tmp_path)
    path = tmp_path / f"{BOOK}.json"
    first = _damage(path)
    store.save_resume_position(book_id=BOOK, char_offset=5, chunk_index=0)
    second = _damage(path)

    store.save_resume_position(book_id=BOOK, char_offset=6, chunk_index=0)

    assert (tmp_path / f"{BOOK}.json.damaged").read_bytes() == first
    assert (tmp_path / f"{BOOK}.json.damaged.2").read_bytes() == second


def test_json_that_is_not_an_object_is_damage_not_a_crash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = tmp_path / f"{BOOK}.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    assert store.list_bookmarks(book_id=BOOK) == []
    store.save_resume_position(book_id=BOOK, char_offset=5, chunk_index=0)

    assert json.loads((tmp_path / f"{BOOK}.json.damaged").read_text()) == [1, 2, 3]


def test_a_file_that_cannot_be_read_is_never_written_over(tmp_path: Path) -> None:
    """A read that fails may be transient; the file may be perfectly good."""

    store = _store(tmp_path)
    unreadable = tmp_path / f"{BOOK}.json"
    unreadable.mkdir()

    with pytest.raises(OSError):
        store.save_resume_position(book_id=BOOK, char_offset=5, chunk_index=0)

    assert unreadable.is_dir()


def test_an_empty_file_holds_nothing_to_keep(tmp_path: Path) -> None:
    store = _store(tmp_path)
    (tmp_path / f"{BOOK}.json").write_bytes(b"  \n")

    store.save_resume_position(book_id=BOOK, char_offset=5, chunk_index=0)

    assert not (tmp_path / f"{BOOK}.json.damaged").exists()
    assert store.load_resume_position(book_id=BOOK) is not None


def test_keeping_aside_on_open_names_the_kept_copy(tmp_path: Path) -> None:
    store = _with_three_bookmarks(tmp_path)
    damaged = _damage(tmp_path / f"{BOOK}.json")

    kept = store.keep_aside_if_damaged(book_id=BOOK)

    assert kept == tmp_path / f"{BOOK}.json.damaged"
    assert kept.read_bytes() == damaged
    assert not (tmp_path / f"{BOOK}.json").exists()


def test_a_sound_or_absent_file_is_left_where_it_is(tmp_path: Path) -> None:
    store = _with_three_bookmarks(tmp_path)

    assert store.keep_aside_if_damaged(book_id=BOOK) is None
    assert store.keep_aside_if_damaged(book_id="never-opened") is None
    assert len(store.list_bookmarks(book_id=BOOK)) == 3


class TestCarryOver:
    """How records saved under an earlier id are found again (N-1)."""

    def test_a_record_moves_to_the_new_id(self, tmp_path: Path) -> None:
        store = _with_three_bookmarks(tmp_path)

        assert store.carry_over(from_id=BOOK, to_id="new-id") is True

        assert len(store.list_bookmarks(book_id="new-id")) == 3
        assert not (tmp_path / f"{BOOK}.json").exists()

    def test_a_record_already_under_the_new_id_wins(self, tmp_path: Path) -> None:
        store = _with_three_bookmarks(tmp_path)
        store.add_bookmark(book_id="new-id", char_offset=1, chunk_index=1)

        assert store.carry_over(from_id=BOOK, to_id="new-id") is False

        assert len(store.list_bookmarks(book_id="new-id")) == 1
        assert len(store.list_bookmarks(book_id=BOOK)) == 3

    def test_nothing_to_carry_is_not_a_fault(self, tmp_path: Path) -> None:
        store = _store(tmp_path)

        assert store.carry_over(from_id=BOOK, to_id="new-id") is False
        assert store.carry_over(from_id=BOOK, to_id=BOOK) is False
