"""The Kindle header reader, against files built to be wrong in one way each."""

from __future__ import annotations

import struct
from pathlib import Path

from voice_reader.infrastructure.shelf import kindle_header

from tests.infrastructure.shelf import mobi_builder


def written(tmp_path: Path, data: bytes, name: str = "book.mobi") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_a_whole_header_is_read(tmp_path: Path) -> None:
    path = written(
        tmp_path,
        mobi_builder.build(
            title="The Shining",
            author="Stephen King",
            publisher="Doubleday",
            subjects=("Horror", "Ghost Stories"),
        ),
    )
    header = kindle_header.read(path)
    assert header.title == "The Shining"
    assert header.author == "Stephen King"
    assert header.publisher == "Doubleday"
    assert header.subjects == ("Horror", "Ghost Stories")
    assert header.has_cover


def test_a_missing_tag_reads_as_empty(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="Stephen King"))
    header = kindle_header.read(path)
    assert header.author == "Stephen King"
    assert header.title == ""
    assert header.publisher == ""


def test_a_blank_subject_is_not_a_subject(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(subjects=("Horror", "   ")))
    assert kindle_header.read(path).subjects == ("Horror",)


def test_a_file_that_is_not_there_states_nothing(tmp_path: Path) -> None:
    header = kindle_header.read(tmp_path / "absent.mobi")
    assert header == kindle_header.KindleHeader()
    assert not header.has_cover


def test_a_file_too_short_to_hold_a_table_states_nothing(tmp_path: Path) -> None:
    assert kindle_header.read(written(tmp_path, b"tiny")).author == ""


def test_a_table_claiming_no_records_states_nothing(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(record_count=0))
    assert kindle_header.read(path).author == ""


def test_a_table_claiming_absurdly_many_records_states_nothing(
    tmp_path: Path,
) -> None:
    data = bytearray(mobi_builder.build(author="A Author"))
    data[76:78] = struct.pack(">H", 65535)
    assert kindle_header.read(written(tmp_path, bytes(data))).author == ""


def test_a_table_running_past_the_end_states_nothing(tmp_path: Path) -> None:
    data = bytearray(mobi_builder.build(author="A Author"))
    data[76:78] = struct.pack(">H", 4000)
    assert kindle_header.read(written(tmp_path, bytes(data))).author == ""


def test_offsets_running_past_the_end_state_nothing(tmp_path: Path) -> None:
    whole = mobi_builder.build(author="A Author")
    truncated = whole[: mobi_builder.PALM_HEADER_BYTES + 3 * 8 + 10]
    assert kindle_header.read(written(tmp_path, truncated)).author == ""


def test_a_record_zero_too_small_states_nothing(tmp_path: Path) -> None:
    header = bytearray(b"\x00" * mobi_builder.PALM_HEADER_BYTES)
    header[76:78] = struct.pack(">H", 1)
    table = struct.pack(">I", mobi_builder.PALM_HEADER_BYTES + 8) + b"\x00" * 4
    data = bytes(header) + table + b"short record"
    assert kindle_header.read(written(tmp_path, data)).author == ""


def test_a_container_that_is_not_mobi_states_nothing(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="A", mobi_magic=b"XXXX"))
    assert kindle_header.read(path).author == ""


def test_a_header_without_the_exth_flag_states_nothing(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="A", with_exth=False))
    assert kindle_header.read(path).author == ""


def test_a_block_that_is_not_exth_states_nothing(tmp_path: Path) -> None:
    data = bytearray(mobi_builder.build(author="A Author"))
    at = data.find(b"EXTH")
    data[at : at + 4] = b"XXXX"
    assert kindle_header.read(written(tmp_path, bytes(data))).author == ""


def test_an_entry_claiming_an_impossible_length_stops_the_read(
    tmp_path: Path,
) -> None:
    """A length under the entry header itself cannot be believed."""

    data = bytearray(
        mobi_builder.build(author="A Author", subjects=("Horror",), cover=None)
    )
    at = data.find(b"EXTH") + 12
    data[at + 4 : at + 8] = struct.pack(">I", 2)
    assert kindle_header.read(written(tmp_path, bytes(data))).author == ""


def test_an_entry_running_past_the_block_stops_the_read(tmp_path: Path) -> None:
    data = bytearray(mobi_builder.build(author="A Author", cover=None))
    at = data.find(b"EXTH") + 12
    data[at + 4 : at + 8] = struct.pack(">I", 4096)
    assert kindle_header.read(written(tmp_path, bytes(data))).author == ""


def test_a_count_larger_than_the_entries_stops_at_the_last_one(
    tmp_path: Path,
) -> None:
    data = bytearray(mobi_builder.build(author="A Author", cover=None))
    at = data.find(b"EXTH")
    data[at + 8 : at + 12] = struct.pack(">I", 500)
    assert kindle_header.read(written(tmp_path, bytes(data))).author == "A Author"


def test_a_book_with_no_cover_record_has_no_cover(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="A Author", cover=None))
    header = kindle_header.read(path)
    assert header.author == "A Author"
    assert header.cover is None


def test_a_cover_offset_of_none_has_no_cover(tmp_path: Path) -> None:
    path = written(
        tmp_path,
        mobi_builder.build(author="A", cover=None, cover_offset=0xFFFFFFFF),
    )
    assert kindle_header.read(path).cover is None


def test_a_cover_offset_past_the_records_has_no_cover(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="A", cover_offset=99))
    assert kindle_header.read(path).cover is None


def test_a_cover_record_that_is_not_an_image_has_no_cover(tmp_path: Path) -> None:
    path = written(tmp_path, mobi_builder.build(author="A", cover=b"not an image"))
    assert kindle_header.read(path).cover is None


def test_a_cover_offset_of_the_wrong_width_has_no_cover(tmp_path: Path) -> None:
    data = bytearray(mobi_builder.build(author="A Author"))
    at = data.find(b"EXTH") + 12
    while True:
        tag, length = struct.unpack(">II", data[at : at + 8])
        if tag == mobi_builder.TAG_COVER_OFFSET:
            break
        at += length
    data[at + 4 : at + 8] = struct.pack(">I", 10)
    header = kindle_header.read(written(tmp_path, bytes(data)))
    assert header.cover is None
