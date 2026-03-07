from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.books.parser import BookParser


def test_parser_txt_normalization(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("Hello\r\n\r\nWorld\t\t!", encoding="utf-8")
    raw, norm = BookParser().parse(p)
    assert "World" in raw
    assert norm == "Hello\n\nWorld !"
