from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from voice_reader.infrastructure.bookmarks.json_bookmark_repository import (
    JSONBookmarkRepository,
    _dt_to_iso_z,
)


def test_dt_to_iso_z_accepts_naive_datetime() -> None:
    # Covers the tzinfo None branch.
    s = _dt_to_iso_z(datetime(2026, 3, 14, 12, 0, 0))
    assert s.endswith("Z")


def test_load_doc_tolerates_invalid_json(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text("{not-json", encoding="utf-8")
    assert repo.list_bookmarks(book_id="b1") == []
    assert repo.load_resume_position(book_id="b1") is None


def test_load_doc_tolerates_resume_wrong_type(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps({"resume": "bad", "bookmarks": []}), encoding="utf-8"
    )
    assert repo.load_resume_position(book_id="b1") is None


def test_list_bookmarks_skips_non_dict_and_invalid_dicts(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps(
            {
                "resume": None,
                "bookmarks": [
                    1,
                    "x",
                    {"bookmark_id": 1},
                    {
                        "bookmark_id": "not-int",
                        "name": "Bookmark 1",
                        "char_offset": 1,
                        "chunk_index": 0,
                        "created_at": "2026-03-14T00:00:00Z",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assert repo.list_bookmarks(book_id="b1") == []


def test_add_bookmark_skips_preexisting_invalid_bookmark_entries(
    tmp_path: Path,
) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps(
            {
                "resume": None,
                "bookmarks": [
                    {"bookmark_id": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    bm = repo.add_bookmark(book_id="b1", char_offset=10, chunk_index=1)
    assert bm.bookmark_id >= 1
    # The stored file should now contain a valid bookmarks list and next_bookmark_id.
    doc = json.loads((tmp_path / "b1.json").read_text(encoding="utf-8"))
    assert isinstance(doc.get("bookmarks"), list)
    assert int(doc.get("next_bookmark_id")) >= 2


def test_delete_bookmark_tolerates_non_int_bookmark_ids(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps(
            {
                "resume": None,
                "bookmarks": [
                    {
                        "bookmark_id": "not-int",
                        "name": "Bookmark X",
                        "char_offset": 1,
                        "chunk_index": 0,
                        "created_at": "2026-03-14T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    repo.delete_bookmark(book_id="b1", bookmark_id=1)


def test_load_resume_position_returns_none_on_parse_error(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps(
            {
                "resume": {
                    "char_offset": 1,
                    "chunk_index": 2,
                    "updated_at": "not-a-date",
                },
                "bookmarks": [],
            }
        ),
        encoding="utf-8",
    )
    assert repo.load_resume_position(book_id="b1") is None


def test_save_resume_position_normalizes_non_list_bookmarks(tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.json").write_text(
        json.dumps({"resume": None, "bookmarks": {"bad": True}}),
        encoding="utf-8",
    )
    repo.save_resume_position(book_id="b1", char_offset=1, chunk_index=2)
    doc = json.loads((tmp_path / "b1.json").read_text(encoding="utf-8"))
    assert isinstance(doc.get("bookmarks"), list)


def test_load_doc_read_text_failure_returns_empty(monkeypatch, tmp_path: Path) -> None:
    repo = JSONBookmarkRepository(bookmarks_dir=tmp_path)
    target = tmp_path / "b1.json"
    target.write_text("{}", encoding="utf-8")

    orig = Path.read_text

    def _boom(self: Path, *a, **k):
        if self.name == "b1.json":
            raise OSError("boom")
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _boom)
    assert repo.list_bookmarks(book_id="b1") == []
