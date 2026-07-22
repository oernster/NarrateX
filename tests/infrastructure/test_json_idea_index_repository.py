from __future__ import annotations

import json
from pathlib import Path

from voice_reader.infrastructure.ideas.json_idea_index_repository import (
    JSONIdeaIndexRepository,
)


def test_load_missing_returns_none(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    assert repo.load_doc(book_id="b1") is None


def test_load_invalid_json_returns_none(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.ideas.json").write_text("{not-json", encoding="utf-8")
    assert repo.load_doc(book_id="b1") is None


def test_load_non_dict_returns_none(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.ideas.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert repo.load_doc(book_id="b1") is None


def test_delete_doc_removes_the_index_and_any_stale_temp(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    (tmp_path / "b1.ideas.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b1.ideas.json.tmp").write_text("{}", encoding="utf-8")

    repo.delete_doc(book_id="b1")

    assert not (tmp_path / "b1.ideas.json").exists()
    assert not (tmp_path / "b1.ideas.json.tmp").exists()


def test_delete_doc_tolerates_a_missing_file(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)

    repo.delete_doc(book_id="never-saved")

    assert repo.load_doc(book_id="never-saved") is None


def test_delete_doc_tolerates_an_unlinkable_path(tmp_path: Path) -> None:
    # A null byte is invalid in a path on every platform, so unlink raises
    # rather than reporting missing; deletion must swallow it.
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)

    repo.delete_doc(book_id="bad\x00id")


def test_save_atomic_writes_file(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    doc = {
        "schema_version": 1,
        "status": {"state": "completed"},
        "book": {"fingerprint_sha256": "x"},
    }
    repo.save_doc_atomic(book_id="b1", doc=doc)
    path = tmp_path / "b1.ideas.json"
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1


def test_save_requires_dict(tmp_path: Path) -> None:
    repo = JSONIdeaIndexRepository(bookmarks_dir=tmp_path)
    try:
        repo.save_doc_atomic(book_id="b1", doc=[])  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("Expected TypeError")
