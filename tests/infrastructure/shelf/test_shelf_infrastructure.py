"""The walker, the sidecar reader, the metadata precedence and the two stores.

Integration rather than unit: real files in a temporary directory, a real
SQLite file, no mock library anywhere.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.infrastructure.shelf import opf
from voice_reader.infrastructure.shelf.index_store import SqliteShelfIndex
from voice_reader.infrastructure.shelf.metadata_reader import ShelfMetadataReader
from voice_reader.infrastructure.shelf.thumbnails import FileThumbnailStore
from voice_reader.infrastructure.shelf.walker import FileSystemWalker

from tests.infrastructure.shelf import mobi_builder

OPF_TEXT = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>The Shining</dc:title>
    <dc:creator opf:role="edt" xmlns:opf="http://www.idpf.org/2007/opf">An Editor</dc:creator>
    <dc:creator opf:role="aut" xmlns:opf="http://www.idpf.org/2007/opf">Stephen King</dc:creator>
    <dc:subject>Horror</dc:subject>
    <dc:subject>Ghost Stories</dc:subject>
  </metadata>
</package>
"""


def key_for(path: Path) -> ShelfKey:
    stat = path.stat()
    return ShelfKey(path=path, size_bytes=stat.st_size, modified_ns=stat.st_mtime_ns)


# The walker ----------------------------------------------------------------


def test_a_walk_finds_the_book_files_and_nothing_else(tmp_path: Path) -> None:
    (tmp_path / "a.mobi").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("this is a book format too")
    (tmp_path / "cover.jpg").write_bytes(b"x")
    nested = tmp_path / "deeper"
    nested.mkdir()
    (nested / "b.epub").write_bytes(b"x")

    result = FileSystemWalker().walk(tmp_path)
    names = sorted(key.path.name for key in result.keys)
    assert names == ["a.mobi", "b.epub", "notes.txt"]
    assert result.root_reachable
    assert result.unreadable == ()


def test_a_root_that_is_not_there_is_unreachable(tmp_path: Path) -> None:
    result = FileSystemWalker().walk(tmp_path / "absent")
    assert not result.root_reachable
    assert result.keys == ()


def test_a_folder_that_refuses_to_open_is_recorded(tmp_path: Path) -> None:
    locked = tmp_path / "locked"

    def refusing_walk(root, onerror=None):
        onerror(PermissionError(13, "denied", str(locked)))
        return iter(())

    result = FileSystemWalker(walk_fn=refusing_walk).walk(tmp_path)
    assert result.unreadable == (locked,)
    assert result.keys == ()


def test_an_error_naming_no_file_falls_back_to_the_root(tmp_path: Path) -> None:
    def refusing_walk(root, onerror=None):
        onerror(OSError("no filename on this one"))
        return iter(())

    result = FileSystemWalker(walk_fn=refusing_walk).walk(tmp_path)
    assert result.unreadable == (tmp_path,)


def test_a_file_that_vanishes_before_the_stat_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "real.mobi").write_bytes(b"x")

    def stale_walk(root, onerror=None):
        del onerror
        return iter([(str(tmp_path), [], ["real.mobi", "gone.mobi"])])

    result = FileSystemWalker(walk_fn=stale_walk).walk(tmp_path)
    assert [key.path.name for key in result.keys] == ["real.mobi"]


# The sidecar ---------------------------------------------------------------


def test_a_sidecar_is_found_beside_the_book(tmp_path: Path) -> None:
    (tmp_path / "metadata.opf").write_text(OPF_TEXT, encoding="utf-8")
    assert opf.sidecar_path(tmp_path / "book.mobi") == tmp_path / "metadata.opf"


def test_no_sidecar_is_not_a_fault(tmp_path: Path) -> None:
    assert opf.sidecar_path(tmp_path / "book.mobi") is None


def test_a_sidecar_states_the_title_the_author_and_the_subjects(
    tmp_path: Path,
) -> None:
    path = tmp_path / "metadata.opf"
    path.write_text(OPF_TEXT, encoding="utf-8")
    stated = opf.read(path)
    assert stated.title == "The Shining"
    assert stated.author == "Stephen King"
    assert stated.subjects == ("Horror", "Ghost Stories")


def test_an_author_with_no_role_is_still_the_author(tmp_path: Path) -> None:
    path = tmp_path / "metadata.opf"
    path.write_text(
        '<package xmlns="http://www.idpf.org/2007/opf">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:creator></dc:creator><dc:creator>Someone Else</dc:creator>"
        "</metadata></package>",
        encoding="utf-8",
    )
    stated = opf.read(path)
    assert stated.author == "Someone Else"
    assert stated.title == ""


def test_a_sidecar_that_is_not_there_states_nothing(tmp_path: Path) -> None:
    assert opf.read(tmp_path / "absent.opf") == opf.OpfMetadata()


def test_a_sidecar_that_will_not_parse_states_nothing(tmp_path: Path) -> None:
    path = tmp_path / "metadata.opf"
    path.write_text("<package><unclosed>", encoding="utf-8")
    assert opf.read(path) == opf.OpfMetadata()


def test_a_sidecar_too_large_to_be_metadata_states_nothing(tmp_path: Path) -> None:
    path = tmp_path / "metadata.opf"
    path.write_bytes(b"<package/>" + b" " * (2 * 1024 * 1024 + 1))
    assert opf.read(path) == opf.OpfMetadata()


# The precedence ------------------------------------------------------------


def test_a_sidecar_outranks_the_file(tmp_path: Path) -> None:
    book = tmp_path / "book.mobi"
    book.write_bytes(mobi_builder.build(title="Embedded", author="Embedded Author"))
    (tmp_path / "metadata.opf").write_text(OPF_TEXT, encoding="utf-8")

    stated = ShelfMetadataReader().read(key_for(book))
    assert stated.title == "The Shining"
    assert stated.author == "Stephen King"
    assert stated.subjects == ("Horror", "Ghost Stories")


def test_the_file_answers_when_no_sidecar_does(tmp_path: Path) -> None:
    book = tmp_path / "book.mobi"
    book.write_bytes(
        mobi_builder.build(
            title="Embedded", author="Embedded Author", subjects=("Crime",)
        )
    )
    stated = ShelfMetadataReader().read(key_for(book))
    assert (stated.title, stated.author) == ("Embedded", "Embedded Author")
    assert stated.subjects == ("Crime",)
    assert stated.has_cover


def test_a_sidecar_cover_counts_even_when_the_opf_is_absent(tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"x")
    (tmp_path / "cover.jpg").write_bytes(b"\xff\xd8 pretend")

    assert ShelfMetadataReader().read(key_for(book)).has_cover


def test_a_format_that_states_nothing_states_nothing(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    book.write_text("plain words", encoding="utf-8")
    stated = ShelfMetadataReader().read(key_for(book))
    assert stated.title == ""
    assert not stated.has_cover


# The index -----------------------------------------------------------------


def entry(path: Path, **kwargs) -> ShelfEntry:
    return ShelfEntry(
        key=ShelfKey(path=path, size_bytes=7, modified_ns=9),
        title=kwargs.pop("title", "A Title"),
        author=kwargs.pop("author", "An Author"),
        **kwargs,
    )


def test_an_empty_index_holds_nothing(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path / "state")
    assert index.load_roots() == ()
    assert index.load_entries() == ()
    assert index.load_stated_genres() == {}
    assert index.path.name.endswith(".sqlite3")


def test_roots_come_back_in_the_order_they_were_saved(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_roots((Path("H:/Books"), Path("D:/Other")))
    assert index.load_roots() == (Path("H:/Books"), Path("D:/Other"))


def test_saving_roots_replaces_the_previous_set(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_roots((Path("H:/Books"),))
    index.save_roots((Path("D:/Other"),))
    assert index.load_roots() == (Path("D:/Other"),)


def test_an_entry_comes_back_exactly_as_it_went_in(tmp_path: Path) -> None:
    original = entry(
        Path("H:/Books/a.mobi"),
        subjects=("Horror", "Crime"),
        book_id="abc",
        total_chars=1234,
        has_cover=True,
    )
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_entries((original,))
    assert index.load_entries() == (original,)


def test_an_entry_with_nothing_optional_comes_back_the_same(tmp_path: Path) -> None:
    original = entry(Path("H:/Books/b.mobi"))
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_entries((original,))
    restored = index.load_entries()[0]
    assert restored.book_id is None
    assert restored.total_chars is None
    assert not restored.has_cover


def test_saving_entries_replaces_the_previous_scan(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_entries((entry(Path("H:/Books/a.mobi")),))
    index.save_entries((entry(Path("H:/Books/b.mobi")),))
    assert [e.key.path.name for e in index.load_entries()] == ["b.mobi"]


def test_what_the_reader_stated_survives_a_rebuild(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_roots((Path("H:/Books"),))
    index.save_entries((entry(Path("H:/Books/a.mobi")),))
    index.save_stated_genres({"king stephen|shining": ("Horror",)})

    index.rebuild_entries()

    assert index.load_entries() == ()
    assert index.load_roots() == (Path("H:/Books"),)
    assert index.load_stated_genres() == {"king stephen|shining": ("Horror",)}


def test_stating_genres_replaces_the_previous_statement(tmp_path: Path) -> None:
    index = SqliteShelfIndex(directory=tmp_path)
    index.save_stated_genres({"one": ("Horror",)})
    index.save_stated_genres({"two": ("Crime", "Mystery")})
    assert index.load_stated_genres() == {"two": ("Crime", "Mystery")}


def test_the_index_survives_being_reopened(tmp_path: Path) -> None:
    SqliteShelfIndex(directory=tmp_path).save_entries((entry(Path("H:/a.mobi")),))
    assert len(SqliteShelfIndex(directory=tmp_path).load_entries()) == 1


# The thumbnails ------------------------------------------------------------


def test_a_thumbnail_comes_back_as_it_went_in(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path / "art")
    store.put("token", b"\xff\xd8image")
    assert store.has("token")
    assert store.get("token") == b"\xff\xd8image"


def test_a_token_never_stored_has_nothing(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path)
    assert not store.has("token")
    assert store.get("token") is None


def test_a_token_with_a_path_in_it_is_still_one_file(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path / "art")
    store.put("king stephen|the shining: complete/uncut", b"\xff\xd8image")
    assert store.get("king stephen|the shining: complete/uncut") == b"\xff\xd8image"


def test_storing_nothing_stores_nothing(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path / "art")
    store.put("token", b"")
    assert not store.has("token")


def test_a_thumbnail_too_large_to_be_one_is_not_returned(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path)
    store.put("token", b"\xff\xd8" + b"x" * (2 * 1024 * 1024 + 1))
    assert store.get("token") is None


def test_a_cache_that_cannot_be_written_is_not_a_stopped_shelf(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "in-the-way"
    blocked.write_text("this is a file, not a directory", encoding="utf-8")
    store = FileThumbnailStore(directory=blocked / "art")

    store.put("token", b"\xff\xd8image")

    assert not store.has("token")


def test_forgetting_one_thumbnail_leaves_the_others(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path)
    store.put("one", b"\xff\xd81")
    store.put("two", b"\xff\xd82")
    store.forget("one")
    assert not store.has("one")
    assert store.has("two")


def test_forgetting_something_never_stored_is_not_a_fault(tmp_path: Path) -> None:
    FileThumbnailStore(directory=tmp_path).forget("never")


def test_clearing_empties_the_cache(tmp_path: Path) -> None:
    store = FileThumbnailStore(directory=tmp_path)
    store.put("one", b"\xff\xd81")
    store.put("two", b"\xff\xd82")
    store.clear()
    assert not store.has("one")
    assert not store.has("two")
