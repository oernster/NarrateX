"""Plain text in an encoding other than UTF-8 is read, not stripped (round 3, N-6).

Text and Markdown were decoded as UTF-8 with errors ignored, so a Windows
(cp1252) file lost every accented letter and curly quote without a word, a
Notepad "Unicode" (UTF-16) file reached the narrator with a NUL between
characters; a UTF-8 byte order mark became the book's first character.
"""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.shared.errors import BookParseError

TEXT = "Le café naïve à l'été. \u201cQuoted\u201d \u2013 dash."


def _parse(tmp_path: Path, data: bytes, suffix: str = ".txt") -> str:
    path = tmp_path / f"book{suffix}"
    path.write_bytes(data)
    return BookParser().parse(path).normalized_text


@pytest.mark.parametrize("suffix", [".txt", ".md"])
def test_windows_text_keeps_its_letters(tmp_path: Path, suffix: str) -> None:
    assert _parse(tmp_path, TEXT.encode("cp1252"), suffix) == TEXT


@pytest.mark.parametrize(
    "bom, codec",
    [
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF8, "utf-8"),
    ],
    ids=["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be", "utf-8-sig"],
)
def test_a_byte_order_mark_names_the_encoding(
    tmp_path: Path, bom: bytes, codec: str
) -> None:
    assert _parse(tmp_path, bom + TEXT.encode(codec)) == TEXT


def test_utf8_without_a_mark_is_read_as_utf8(tmp_path: Path) -> None:
    assert _parse(tmp_path, TEXT.encode("utf-8")) == TEXT


def test_bytes_no_encoding_reads_cleanly_are_refused_with_a_reason(
    tmp_path: Path,
) -> None:
    # 0x81 is undefined in cp1252 and cannot start a UTF-8 character.
    with pytest.raises(BookParseError, match="encoding"):
        _parse(tmp_path, b"Plain words \x81 then more")


def test_a_marked_file_that_does_not_decode_is_refused(tmp_path: Path) -> None:
    # A UTF-16 mark followed by an odd number of bytes is not UTF-16.
    with pytest.raises(BookParseError, match="encoding"):
        _parse(tmp_path, codecs.BOM_UTF16_LE + b"abc")
