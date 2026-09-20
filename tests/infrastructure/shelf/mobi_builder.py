"""Build a minimal Kindle container, so the header reader is tested on one.

A real `.mobi` from the reference library cannot be a fixture: the suite has to
run on a machine with no H: drive. This writes the smallest file the format
allows, which also lets a test damage one part at a time and see what the
reader does about it.
"""

from __future__ import annotations

import struct

PALM_HEADER_BYTES = 78
RECORD_ENTRY_BYTES = 8
MOBI_HEADER_BYTES = 232
EXTH_PRESENT_FLAG = 0x40

TAG_AUTHOR = 100
TAG_PUBLISHER = 101
TAG_SUBJECT = 105
TAG_COVER_OFFSET = 201
TAG_UPDATED_TITLE = 503

JPEG = b"\xff\xd8" + b"fake jpeg body"


def _exth(entries: list[tuple[int, bytes]]) -> bytes:
    body = b""
    for tag, payload in entries:
        body += struct.pack(">II", tag, 8 + len(payload)) + payload
    block = b"EXTH" + struct.pack(">II", 12 + len(body), len(entries)) + body
    padding = (-len(block)) % 4
    return block + b"\x00" * padding


def _mobi_header(*, first_image_index: int, with_exth: bool) -> bytes:
    header = bytearray(b"\x00" * MOBI_HEADER_BYTES)
    header[0:4] = b"MOBI"
    header[4:8] = struct.pack(">I", MOBI_HEADER_BYTES)
    # Record-zero offset 108 is 92 bytes into the header, which starts at 16.
    header[92:96] = struct.pack(">I", first_image_index)
    header[112:116] = struct.pack(">I", EXTH_PRESENT_FLAG if with_exth else 0)
    return bytes(header)


def build(
    *,
    title: str = "",
    author: str = "",
    publisher: str = "",
    subjects: tuple[str, ...] = (),
    cover: bytes | None = JPEG,
    with_exth: bool = True,
    mobi_magic: bytes = b"MOBI",
    cover_offset: int | None = None,
    record_count: int | None = None,
) -> bytes:
    """One PalmDB file, valid unless a test asks for it to be otherwise."""

    images = [cover] if cover is not None else []
    first_image_index = 1

    entries: list[tuple[int, bytes]] = []
    if author:
        entries.append((TAG_AUTHOR, author.encode("utf-8")))
    if publisher:
        entries.append((TAG_PUBLISHER, publisher.encode("utf-8")))
    for subject in subjects:
        entries.append((TAG_SUBJECT, subject.encode("utf-8")))
    if title:
        entries.append((TAG_UPDATED_TITLE, title.encode("utf-8")))
    if cover is not None or cover_offset is not None:
        offset = 0 if cover_offset is None else cover_offset
        entries.append((TAG_COVER_OFFSET, struct.pack(">I", offset)))

    record_zero = (
        b"\x00" * 16
        + _mobi_header(first_image_index=first_image_index, with_exth=with_exth)
        + (_exth(entries) if with_exth else b"")
    )
    record_zero = record_zero[:16] + mobi_magic + record_zero[20:]

    records = [record_zero] + images
    stated = len(records) if record_count is None else record_count

    table_bytes = stated * RECORD_ENTRY_BYTES
    start = PALM_HEADER_BYTES + table_bytes
    offsets = []
    position = start
    for record in records:
        offsets.append(position)
        position += len(record)

    header = bytearray(b"\x00" * PALM_HEADER_BYTES)
    header[76:78] = struct.pack(">H", stated)
    table = b""
    for index in range(stated):
        offset = offsets[index] if index < len(offsets) else position
        table += struct.pack(">I", offset) + b"\x00\x00\x00\x00"

    return bytes(header) + table + b"".join(records)
