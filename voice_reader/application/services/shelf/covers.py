"""The picture on a tile: read once, kept, never read during a scan.

FR-BS-030 to FR-BS-038. The cover work is the expensive half of the shelf, so
this service exists to make sure it happens at most once per work and only for a
work the reader is actually looking at.

**Nothing here runs during a scan.** A scan records what a file states about
itself; the picture is read when a tile is about to be drawn (FR-BS-038) and the
small copy is kept (FR-BS-034), so a shelf reopened draws from the cache without
opening a book file at all.

**A work with no picture is remembered as such.** Without that, every redraw
would re-read every coverless file looking for a cover that was not there the
last four times. The memory of a miss is deliberately not persisted: a cover
added beside a book should appear on the next run, not never.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voice_reader.domain.interfaces.shelf_ports import (
    BookCoverSource,
    ThumbnailMaker,
    ThumbnailStore,
)
from voice_reader.domain.shelf.works import Work

# The size the kept copy holds. The grid draws smaller than this, which keeps a
# tile crisp on a display scaled past 100%.
#
# Measured over the reference library on 2026-09-20: 673 pictures at this size,
# encoded as PNG, came to 103 MB, so about 157 KB each. That is the price of a
# lossless copy and it sits in the cache directory, which is derived and
# deletable; the lever if it ever matters is this size, not the format.
THUMBNAIL_WIDTH = 320
THUMBNAIL_HEIGHT = 480


@dataclass(frozen=True, slots=True)
class ShelfCovers:
    """Answers one work's thumbnail, reading the book only when it must."""

    covers: BookCoverSource
    thumbnails: ThumbnailStore
    maker: ThumbnailMaker
    width: int = THUMBNAIL_WIDTH
    height: int = THUMBNAIL_HEIGHT
    # Works asked for and found to have no picture, this run only.
    _misses: set[str] = field(default_factory=set)

    def thumbnail(self, work: Work) -> bytes | None:
        """The small copy of this work's cover; None when it has none.

        Answered from the cache where it is held. Otherwise every file the work
        holds is asked in turn, the first picture found is reduced and kept; a
        work that yields nothing is remembered so the files are not read again.
        """

        token = work.token
        held = self.thumbnails.get(token)
        if held is not None:
            return held
        if token in self._misses:
            return None
        small = self._read(work)
        if small is None:
            self._misses.add(token)
            return None
        self.thumbnails.put(token, small)
        return small

    def held_for(self, work: Work) -> bytes | None:
        """The kept copy, without reading any file. None means not yet read.

        This is what a paint answers from: drawing must never wait on a disk,
        so a tile draws its placeholder and the picture arrives on a later paint.
        """

        return self.thumbnails.get(work.token)

    def known_absent(self, work: Work) -> bool:
        """True where this work has already been found to have no picture."""

        return work.token in self._misses

    def forget(self, work: Work) -> None:
        """Drop the kept copy, so the next ask reads the files again."""

        self.thumbnails.forget(work.token)
        self._misses.discard(work.token)

    def _read(self, work: Work) -> bytes | None:
        for entry in work.cover_candidates:
            raw = self.covers.cover_bytes(entry.key)
            if not raw:
                continue
            small = self.maker.downscale(raw, width=self.width, height=self.height)
            if small:
                return small
        return None
