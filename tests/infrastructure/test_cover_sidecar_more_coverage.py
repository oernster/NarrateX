"""Cover the sidecar search and its guarded reads.

A sidecar cover is whatever image happens to sit beside the book file, so the
search runs against a real directory the test builds. The only stand-ins are
for the failures a directory cannot be made to produce on demand: a path whose
existence check is refused, and a directory that will not enumerate.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.books.cover._io_utils import safe_read_image_bytes
from voice_reader.infrastructure.books.cover.sidecar import (
    extract_sidecar_image_with_path,
    resolve_calibre_sidecar_cover_path,
)

_MAX_BYTES = 1024 * 1024

_CALIBRE_COVER_NAMES = frozenset({"cover.jpg", "cover.jpeg", "cover.png", "cover.webp"})


class RefusingPath(type(Path())):
    """A path that refuses the existence check for exact Calibre cover names."""

    def exists(self) -> bool:
        if self.name in _CALIBRE_COVER_NAMES:
            raise PermissionError(self.name)
        return super().exists()


class UnlistablePath(type(Path())):
    """A directory that exists but will not enumerate its contents."""

    def iterdir(self):
        raise PermissionError(str(self))


def test_missing_folder_yields_no_deterministic_cover(tmp_path: Path) -> None:
    book = tmp_path / "gone" / "Book.epub"

    assert resolve_calibre_sidecar_cover_path(book) is None


def test_missing_folder_yields_no_sidecar(tmp_path: Path) -> None:
    book = tmp_path / "gone" / "Book.epub"

    assert extract_sidecar_image_with_path(book, max_bytes=_MAX_BYTES) == (None, None)


def test_a_refused_candidate_is_passed_over(tmp_path: Path) -> None:
    (tmp_path / "cover.jpg").write_bytes(b"JPG")
    book = RefusingPath(tmp_path) / "Book.epub"

    assert resolve_calibre_sidecar_cover_path(book) is None


def test_the_exact_cover_wins_and_reports_its_path(tmp_path: Path) -> None:
    (tmp_path / "cover.png").write_bytes(b"PNG")
    book = tmp_path / "Book.epub"

    data, path = extract_sidecar_image_with_path(book, max_bytes=_MAX_BYTES)

    assert data == b"PNG"
    assert path == tmp_path / "cover.png"


def test_a_common_stem_is_used_when_no_exact_cover_exists(tmp_path: Path) -> None:
    (tmp_path / "folder.gif").write_bytes(b"GIF")
    book = tmp_path / "Book.epub"

    data, path = extract_sidecar_image_with_path(book, max_bytes=_MAX_BYTES)

    assert data == b"GIF"
    assert path == tmp_path / "folder.gif"


def test_the_scan_ranks_named_images_and_ignores_directories(tmp_path: Path) -> None:
    # A directory can carry an image suffix; it is not a candidate.
    (tmp_path / "covers.png").mkdir()
    (tmp_path / "my_folder.png").write_bytes(b"RANK3")
    (tmp_path / "folder_shot.png").write_bytes(b"RANK2")
    (tmp_path / "my_cover.png").write_bytes(b"RANK1")
    (tmp_path / "cover_front.png").write_bytes(b"RANK0")
    book = tmp_path / "Book.epub"

    data, path = extract_sidecar_image_with_path(book, max_bytes=_MAX_BYTES)

    assert data == b"RANK0"
    assert path == tmp_path / "cover_front.png"


def test_an_unlistable_folder_yields_nothing(tmp_path: Path) -> None:
    book = UnlistablePath(tmp_path) / "Book.epub"

    assert extract_sidecar_image_with_path(book, max_bytes=_MAX_BYTES) == (None, None)


def test_an_oversized_image_is_not_read(tmp_path: Path) -> None:
    image = tmp_path / "cover.jpg"
    image.write_bytes(b"0123456789")

    assert safe_read_image_bytes(image, max_bytes=1) is None
    assert safe_read_image_bytes(image, max_bytes=None) == b"0123456789"


def test_an_unmeasurable_image_is_not_read() -> None:
    class Unmeasurable:
        def exists(self) -> bool:
            return True

        def is_file(self) -> bool:
            return True

        def stat(self):
            raise OSError("size unavailable")

    assert safe_read_image_bytes(Unmeasurable(), max_bytes=_MAX_BYTES) is None


def test_an_unreadable_image_yields_nothing() -> None:
    class Unreadable:
        def exists(self) -> bool:
            return True

        def is_file(self) -> bool:
            return True

        def read_bytes(self) -> bytes:
            raise OSError("read failed")

    assert safe_read_image_bytes(Unreadable(), max_bytes=None) is None
