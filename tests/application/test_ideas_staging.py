from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.ideas_staging import stage_normalized_text


def test_stage_normalized_text_writes_file(tmp_path: Path) -> None:
    p = stage_normalized_text(work_dir=tmp_path, book_id="b1", normalized_text="hello")
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "hello"


def test_stage_normalized_text_uses_book_fallback_when_book_id_empty(
    tmp_path: Path,
) -> None:
    p = stage_normalized_text(work_dir=tmp_path, book_id=" ", normalized_text="x")
    assert p.name.startswith("book.")


def test_stage_normalized_text_sanitizes_book_id_chars(tmp_path: Path) -> None:
    p = stage_normalized_text(work_dir=tmp_path, book_id="b/1:2", normalized_text="x")
    assert p.name.startswith("b_1_2.")
