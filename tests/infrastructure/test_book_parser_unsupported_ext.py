from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.shared.errors import BookParseError


def test_parser_raises_on_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "a.docx"
    p.write_bytes(b"x")
    with pytest.raises(BookParseError):
        BookParser().parse(p)
