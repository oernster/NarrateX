"""Reading a Kindle file's own header, with no conversion and no process.

FR-BS-031 and FR-BS-032. `.mobi`, `.azw`, `.azw3` and `.prc` are PalmDB
containers: a record table, a MOBI header inside the first record and an EXTH
block of tagged strings after it. The cover is one of the image records and the
author, title and subjects are EXTH tags, so all of them are a file read away.

**Why this exists rather than Calibre.** Measured on 2026-09-19 over the
reference library: one `ebook-convert` costs 2.3 seconds, which is about 54
minutes over 2784 files. Reading the header directly costs 1.3 ms for a `.mobi`
and 7 ms for an `.azw3`, so the same library is 5 seconds. It recovered 2296 of
2784 covers and an author for every file sampled.

**Everything here distrusts the file.** The offsets and counts come from a file
that any tool may have written, so nothing is read past the end, no count is
believed and a malformed file answers nothing rather than raising.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# PalmDB: the record count sits at 76, then eight bytes per record entry whose
# first four are the offset.
_RECORD_COUNT_AT = 76
_RECORD_TABLE_AT = 78
_RECORD_ENTRY_BYTES = 8

# Inside record zero: the MOBI magic, the header length, the index of the first
# image record and the EXTH flags.
_MOBI_MAGIC_AT = 16
_MOBI_HEADER_LENGTH_AT = 20
_FIRST_IMAGE_INDEX_AT = 108
_EXTH_FLAGS_AT = 128
_EXTH_PRESENT_FLAG = 0x40

# EXTH tags. Numbered by the format, not by us.
_TAG_AUTHOR = 100
_TAG_PUBLISHER = 101
_TAG_SUBJECT = 105
_TAG_COVER_OFFSET = 201
_TAG_UPDATED_TITLE = 503

_NO_COVER = 0xFFFFFFFF
_COVER_OFFSET_BYTES = 4
_EXTH_ENTRY_HEADER_BYTES = 8

# A record table that claims more records than a book could hold is a corrupt
# file, not a large one. The reference library's largest holds a few thousand.
_MAX_RECORDS = 100_000

_IMAGE_MAGICS = (b"\xff\xd8", b"\x89P", b"GIF8")


@dataclass(frozen=True, slots=True)
class KindleHeader:
    """What one Kindle file's header stated."""

    title: str = ""
    author: str = ""
    publisher: str = ""
    subjects: tuple[str, ...] = field(default_factory=tuple)
    cover: bytes | None = None

    @property
    def has_cover(self) -> bool:
        return bool(self.cover)


def _records(data: bytes) -> tuple[tuple[int, int], ...]:
    """The byte range of every PalmDB record; empty when the table is unusable."""

    if len(data) < _RECORD_TABLE_AT:
        return ()
    count = struct.unpack(">H", data[_RECORD_COUNT_AT:_RECORD_TABLE_AT])[0]
    if count == 0 or count > _MAX_RECORDS:
        return ()
    table_end = _RECORD_TABLE_AT + count * _RECORD_ENTRY_BYTES
    if table_end > len(data):
        return ()
    offsets = []
    for index in range(count):
        at = _RECORD_TABLE_AT + index * _RECORD_ENTRY_BYTES
        offsets.append(struct.unpack(">I", data[at : at + 4])[0])
    offsets.append(len(data))
    ranges = []
    for index in range(count):
        start, end = offsets[index], offsets[index + 1]
        if start > end or end > len(data):
            return ()
        ranges.append((start, end))
    return tuple(ranges)


def _exth_entries(record_zero: bytes) -> dict[int, list[bytes]]:
    """Every EXTH tag in record zero; empty when there is no usable block."""

    if len(record_zero) < _EXTH_FLAGS_AT + 4:
        return {}
    if record_zero[_MOBI_MAGIC_AT : _MOBI_MAGIC_AT + 4] != b"MOBI":
        return {}
    flags = struct.unpack(">I", record_zero[_EXTH_FLAGS_AT : _EXTH_FLAGS_AT + 4])[0]
    if not flags & _EXTH_PRESENT_FLAG:
        return {}
    header_length = struct.unpack(
        ">I", record_zero[_MOBI_HEADER_LENGTH_AT : _MOBI_HEADER_LENGTH_AT + 4]
    )[0]
    block = record_zero[_MOBI_MAGIC_AT + header_length :]
    if block[:4] != b"EXTH" or len(block) < 12:
        return {}
    count = struct.unpack(">I", block[8:12])[0]
    entries: dict[int, list[bytes]] = {}
    position = 12
    for _ in range(min(count, _MAX_RECORDS)):
        if position + _EXTH_ENTRY_HEADER_BYTES > len(block):
            break
        tag, length = struct.unpack(">II", block[position : position + 8])
        if length < _EXTH_ENTRY_HEADER_BYTES or position + length > len(block):
            break
        entries.setdefault(tag, []).append(
            block[position + _EXTH_ENTRY_HEADER_BYTES : position + length]
        )
        position += length
    return entries


def _text(entries: dict[int, list[bytes]], tag: int) -> str:
    values = entries.get(tag)
    if not values:
        return ""
    return values[0].decode("utf-8", "replace").strip()


def _cover(
    data: bytes,
    records: tuple[tuple[int, int], ...],
    record_zero: bytes,
    entries: dict[int, list[bytes]],
) -> bytes | None:
    values = entries.get(_TAG_COVER_OFFSET)
    if not values or len(values[0]) != _COVER_OFFSET_BYTES:
        return None
    offset = struct.unpack(">I", values[0])[0]
    if offset == _NO_COVER:
        return None
    # Record zero is at least 132 bytes by the time an EXTH block has been
    # found in it, so the first-image index is always inside it. No guard for
    # that, because a guard against the impossible reads as a warning.
    first_image = struct.unpack(
        ">I", record_zero[_FIRST_IMAGE_INDEX_AT : _FIRST_IMAGE_INDEX_AT + 4]
    )[0]
    index = first_image + offset
    if index >= len(records):
        return None
    start, end = records[index]
    image = data[start:end]
    if not image.startswith(_IMAGE_MAGICS):
        return None
    return image


def read(path: Path) -> KindleHeader:
    """What this Kindle file states about itself.

    A file that is not a PalmDB container answers an empty header, as does one
    whose header cannot be trusted. That is an answer, not a fault: the caller falls
    back to the filename, which is what FR-BS-021 asks for.
    """

    try:
        data = path.read_bytes()
    except OSError:
        return KindleHeader()

    records = _records(data)
    if not records:
        return KindleHeader()
    start, end = records[0]
    record_zero = data[start:end]
    entries = _exth_entries(record_zero)
    if not entries:
        return KindleHeader()

    subjects = tuple(
        value.decode("utf-8", "replace").strip()
        for value in entries.get(_TAG_SUBJECT, [])
        if value.strip()
    )
    return KindleHeader(
        title=_text(entries, _TAG_UPDATED_TITLE),
        author=_text(entries, _TAG_AUTHOR),
        publisher=_text(entries, _TAG_PUBLISHER),
        subjects=subjects,
        cover=_cover(data, records, record_zero, entries),
    )
