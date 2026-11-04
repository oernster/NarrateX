"""Write a zip archive from members compressed elsewhere, in parallel.

zipfile compresses each member itself while writing it, one at a time, so a
build cannot hand it work done on other cores. This writes the same archive
from members already compressed: each is LZMA in exactly the form zipfile
writes and reads (its own LZMACompressor makes the bytes), laid out as
PKWARE's APPNOTE describes, with the field values zipfile uses for LZMA.

It writes the classic format only. The payload is far inside its limits; a
bundle that ever outgrows them is refused rather than written corrupt.
"""

from __future__ import annotations

import hashlib
import struct
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

# APPNOTE 4.4.5: compression method 14 is LZMA; 4.4.3: it needs version 6.3.
LZMA_METHOD = zipfile.ZIP_LZMA
LZMA_VERSION = zipfile.LZMA_VERSION
# APPNOTE 4.4.4: bit 1 says the LZMA stream ends with an end marker, as
# zipfile's compressor writes it; bit 11 says the name is UTF-8.
FLAG_LZMA_END_MARKER = 0x0002
FLAG_UTF8_NAME = 0x0800
# Every member carries one fixed time so the payload is reproducible: MS-DOS
# date fields for 1 January 1980, the earliest date the format can hold.
DOS_TIME = 0
DOS_DATE = (1 << 5) | 1

_LOCAL = struct.Struct(zipfile.structFileHeader)
_CENTRAL = struct.Struct(zipfile.structCentralDir)
_END = struct.Struct(zipfile.structEndArchive)
CLASSIC_COUNT_LIMIT = zipfile.ZIP_FILECOUNT_LIMIT
CLASSIC_SIZE_LIMIT = zipfile.ZIP64_LIMIT


@dataclass(frozen=True, slots=True)
class PackedMember:
    """One file, read, hashed and compressed, ready to be written."""

    name: str
    size: int
    crc: int
    sha256: str
    blob: bytes


def pack(path: Path, name: str) -> PackedMember:
    """Read, hash and compress one file; safe to run on any thread."""

    data = path.read_bytes()
    compressor = zipfile.LZMACompressor()
    blob = compressor.compress(data) + compressor.flush()
    return PackedMember(
        name=name,
        size=len(data),
        crc=zlib.crc32(data),
        sha256=hashlib.sha256(data).hexdigest(),
        blob=blob,
    )


def _check_classic(value: int, what: str) -> None:
    if value >= CLASSIC_SIZE_LIMIT:
        raise ValueError(f"{what} needs ZIP64, which this writer does not write")


def write_zip(out: BinaryIO, members: Iterable[PackedMember]) -> int:
    """Write every member, then the central directory; answer the count."""

    central: list[bytes] = []
    for member in members:
        encoded = member.name.encode("utf-8")
        flags = FLAG_LZMA_END_MARKER
        if not member.name.isascii():
            flags |= FLAG_UTF8_NAME
        offset = out.tell()
        for value, what in (
            (offset, "an offset"),
            (member.size, member.name),
            (len(member.blob), member.name),
        ):
            _check_classic(value, what)
        fields = (
            flags,
            LZMA_METHOD,
            DOS_TIME,
            DOS_DATE,
            member.crc,
            len(member.blob),
            member.size,
            len(encoded),
        )
        out.write(_LOCAL.pack(zipfile.stringFileHeader, LZMA_VERSION, 0, *fields, 0))
        out.write(encoded)
        out.write(member.blob)
        central.append(
            _CENTRAL.pack(
                zipfile.stringCentralDir,
                LZMA_VERSION,
                0,
                LZMA_VERSION,
                0,
                *fields,
                0,
                0,
                0,
                0,
                0,
                offset,
            )
            + encoded
        )
    if len(central) > CLASSIC_COUNT_LIMIT:
        raise ValueError(f"{len(central)} members need ZIP64")
    start = out.tell()
    for record in central:
        out.write(record)
    size = out.tell() - start
    _check_classic(start, "the central directory")
    out.write(
        _END.pack(
            zipfile.stringEndArchive, 0, 0, len(central), len(central), size, start, 0
        )
    )
    return len(central)
