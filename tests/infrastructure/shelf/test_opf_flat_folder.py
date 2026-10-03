"""A sidecar speaks for one book, not for a folder (audit round 3, N-4).

Calibre keeps one book per folder, in as many formats as it holds, beside one
`metadata.opf`. A stray sidecar in a flat folder of many books used to retitle
every one of them, so they folded into a single tile and the rest were lost
from the shelf.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from voice_reader.domain.shelf.identity import ShelfKey
from voice_reader.infrastructure.shelf import opf
from voice_reader.infrastructure.shelf.metadata_reader import ShelfMetadataReader

DUNE_OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Dune</dc:title>
    <dc:creator>Frank Herbert</dc:creator>
  </metadata>
</package>
"""


def _key(path: Path) -> ShelfKey:
    path.write_text("text", encoding="utf-8")
    return ShelfKey(path=path, size_bytes=4, modified_ns=0)


def test_a_sidecar_among_many_books_speaks_for_none_of_them(tmp_path: Path) -> None:
    (tmp_path / "metadata.opf").write_text(DUNE_OPF, encoding="utf-8")
    keys = [
        _key(tmp_path / name)
        for name in ("Emma - Jane Austen.txt", "Dracula - Bram Stoker.txt")
    ]

    titles = [ShelfMetadataReader().read(key).title for key in keys]

    assert titles == ["", ""]
    assert opf.sidecar_path(keys[0].path) is None


def test_calibre_layout_keeps_its_sidecar_for_every_format(tmp_path: Path) -> None:
    (tmp_path / "metadata.opf").write_text(DUNE_OPF, encoding="utf-8")
    epub = _key(tmp_path / "Dune - Frank Herbert.epub")
    mobi = _key(tmp_path / "Dune - Frank Herbert.mobi")
    (tmp_path / "cover.jpg").write_bytes(b"not a book")

    for key in (epub, mobi):
        assert ShelfMetadataReader().read(key).title == "Dune"


def test_a_folder_that_cannot_be_listed_trusts_no_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    """Unknown company is not proof of being alone."""

    def refuse(path):
        raise PermissionError(path)

    (tmp_path / "metadata.opf").write_text(DUNE_OPF, encoding="utf-8")
    book = _key(tmp_path / "Dune.epub")
    monkeypatch.setattr(opf, "os", SimpleNamespace(scandir=refuse))

    assert opf.sidecar_path(book.path) is None


def test_a_book_added_to_the_folder_later_is_seen(tmp_path: Path) -> None:
    """The folder listing is not trusted past a change to the folder."""

    (tmp_path / "metadata.opf").write_text(DUNE_OPF, encoding="utf-8")
    first = _key(tmp_path / "Dune.epub")
    assert opf.sidecar_path(first.path) == tmp_path / "metadata.opf"

    _key(tmp_path / "Emma.txt")

    assert opf.sidecar_path(first.path) is None
