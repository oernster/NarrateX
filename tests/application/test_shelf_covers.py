"""The cover service: read once, kept, never read twice for nothing.

Hand-written stand-ins for the three ports, each counting what it was asked, so
the assertions are about how many times a file was touched rather than about what
came back. That is the whole point of the service.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.shelf.covers import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    ShelfCovers,
)
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.works import Work


class _Source:
    def __init__(self, answers: dict[str, bytes] | None = None) -> None:
        self.answers = answers or {}
        self.asked: list[str] = []

    def cover_bytes(self, key: ShelfKey) -> bytes | None:
        self.asked.append(key.path.name)
        return self.answers.get(key.path.name)


class _Store:
    def __init__(self) -> None:
        self.held: dict[str, bytes] = {}
        self.reads = 0

    def has(self, token: str) -> bool:
        return token in self.held

    def get(self, token: str) -> bytes | None:
        self.reads += 1
        return self.held.get(token)

    def put(self, token: str, image: bytes) -> None:
        self.held[token] = image

    def forget(self, token: str) -> None:
        self.held.pop(token, None)

    def clear(self) -> None:
        self.held.clear()


class _Maker:
    def __init__(self, fails: bool = False) -> None:
        self.fails = fails
        self.sizes: list[tuple[int, int]] = []

    def downscale(self, image: bytes, *, width: int, height: int) -> bytes | None:
        self.sizes.append((width, height))
        if self.fails:
            return None
        return b"small:" + image


def _entry(name: str, *, has_cover: bool = False) -> ShelfEntry:
    key = ShelfKey(path=Path("H:/Books") / name, size_bytes=1, modified_ns=1)
    return ShelfEntry(
        key=key, title="Dune", author="Frank Herbert", has_cover=has_cover
    )


def _work(*entries: ShelfEntry) -> Work:
    return Work(title="Dune", author="Frank Herbert", entries=tuple(entries))


def test_a_cover_is_read_reduced_and_kept() -> None:
    source = _Source({"dune.epub": b"big"})
    store = _Store()
    maker = _Maker()
    service = ShelfCovers(covers=source, thumbnails=store, maker=maker)
    work = _work(_entry("dune.epub"))

    assert service.thumbnail(work) == b"small:big"

    assert store.held[work.token] == b"small:big"
    assert maker.sizes == [(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)]


def test_the_kept_copy_answers_the_second_ask() -> None:
    """FR-BS-034: a redraw must not re-read the book."""

    source = _Source({"dune.epub": b"big"})
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker())
    work = _work(_entry("dune.epub"))

    service.thumbnail(work)
    service.thumbnail(work)

    assert source.asked == ["dune.epub"]


def test_a_work_with_no_cover_is_asked_for_only_once() -> None:
    source = _Source()
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker())
    work = _work(_entry("notes.txt"))

    assert service.thumbnail(work) is None
    assert service.thumbnail(work) is None

    assert source.asked == ["notes.txt"]
    assert service.known_absent(work)


def test_the_file_that_states_a_cover_is_asked_first() -> None:
    """The book is opened from the EPUB; the picture may only be in the Kindle file."""

    source = _Source({"dune.azw3": b"kindle"})
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker())
    work = _work(_entry("dune.epub"), _entry("dune.azw3", has_cover=True))

    assert service.thumbnail(work) == b"small:kindle"
    assert source.asked == ["dune.azw3"]


def test_every_file_is_tried_before_giving_up() -> None:
    source = _Source({"dune.pdf": b"raster"})
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker())
    work = _work(_entry("dune.epub"), _entry("dune.pdf"))

    assert service.thumbnail(work) == b"small:raster"
    assert source.asked == ["dune.epub", "dune.pdf"]


def test_an_image_that_will_not_reduce_leaves_the_work_without_one() -> None:
    source = _Source({"dune.epub": b"not really an image"})
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker(fails=True))
    work = _work(_entry("dune.epub"))

    assert service.thumbnail(work) is None
    assert service.known_absent(work)


def test_holding_answers_without_reading_anything() -> None:
    """What a paint uses: the cache, never the disk."""

    source = _Source({"dune.epub": b"big"})
    service = ShelfCovers(covers=source, thumbnails=_Store(), maker=_Maker())
    work = _work(_entry("dune.epub"))

    assert service.held_for(work) is None
    assert source.asked == []

    service.thumbnail(work)
    assert service.held_for(work) == b"small:big"


def test_forgetting_a_work_lets_its_files_be_read_again() -> None:
    source = _Source()
    store = _Store()
    service = ShelfCovers(covers=source, thumbnails=store, maker=_Maker())
    work = _work(_entry("notes.txt"))
    service.thumbnail(work)

    service.forget(work)

    assert not service.known_absent(work)
    assert service.thumbnail(work) is None
    assert source.asked == ["notes.txt", "notes.txt"]
