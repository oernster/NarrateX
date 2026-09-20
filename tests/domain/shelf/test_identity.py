"""The two identities: the cheap shelf key and the lazily resolved book id."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.domain.shelf import text
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey, entry_from_filename


def key(path: str = "H:/Books/a.azw3", size: int = 10, modified: int = 20) -> ShelfKey:
    return ShelfKey(path=Path(path), size_bytes=size, modified_ns=modified)


def test_a_key_states_path_size_and_time() -> None:
    assert key().token == "H:/Books/a.azw3|10|20"


@pytest.mark.parametrize(("size", "modified"), [(-1, 0), (0, -1)])
def test_a_key_refuses_a_negative_measurement(size: int, modified: int) -> None:
    with pytest.raises(ValueError):
        ShelfKey(path=Path("a.epub"), size_bytes=size, modified_ns=modified)


def test_unchanged_from_compares_all_three_parts() -> None:
    assert key().unchanged_from(key())
    assert not key().unchanged_from(key(size=11))
    assert not key().unchanged_from(key(modified=21))
    assert not key().unchanged_from(key(path="H:/Books/b.azw3"))


def test_an_entry_needs_a_title() -> None:
    with pytest.raises(ValueError):
        ShelfEntry(key=key(), title="  ", author="Someone")


def test_an_entry_reports_its_format() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B")
    assert entry.suffix == ".azw3"
    assert entry.needs_conversion
    assert entry.preference_rank > 0


def test_an_epub_entry_needs_no_conversion() -> None:
    entry = ShelfEntry(key=key(path="H:/Books/a.epub"), title="A", author="B")
    assert not entry.needs_conversion
    assert entry.preference_rank == 0


def test_a_new_entry_has_no_book_id() -> None:
    assert ShelfEntry(key=key(), title="A", author="B").book_id is None


def test_a_book_id_is_recorded_once_the_book_has_been_opened() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B").with_book_id("abc123")
    assert entry.book_id == "abc123"


def test_an_empty_book_id_is_refused() -> None:
    with pytest.raises(ValueError):
        ShelfEntry(key=key(), title="A", author="B").with_book_id("  ")


def test_metadata_from_a_better_source_replaces_only_what_it_states() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B", subjects=("Horror",))
    better = entry.with_metadata(title="Real Title")
    assert better.title == "Real Title"
    assert better.author == "B"
    assert better.subjects == ("Horror",)


def test_metadata_can_replace_author_and_subjects() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B")
    better = entry.with_metadata(author="Real Author", subjects=("Fantasy",))
    assert (better.author, better.subjects) == ("Real Author", ("Fantasy",))


def test_two_spellings_of_one_book_share_a_work_key() -> None:
    first = ShelfEntry(key=key(), title="2010: Odyssey Two", author="Arthur C. Clarke")
    second = ShelfEntry(
        key=key(path="H:/Books/b.mobi"),
        title="2010 Odyssey Two",
        author="Arthur C Clarke",
    )
    assert first.work_key == second.work_key


def test_an_entry_built_from_a_filename_reads_title_and_author() -> None:
    entry = entry_from_filename(key(path="H:/Books/A Wanted Man - Child, Lee.azw3"))
    assert (entry.title, entry.author) == ("A Wanted Man", "Lee Child")
    assert entry.book_id is None
    assert entry.subjects == ()


def test_an_entry_built_from_a_bare_filename_has_no_author() -> None:
    entry = entry_from_filename(key(path="H:/Books/book1.azw3"))
    assert entry.author == text.UNKNOWN_AUTHOR


def test_a_length_that_is_not_positive_is_refused() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B")
    for impossible in (0, -1):
        try:
            entry.with_book_id("abc", total_chars=impossible)
        except ValueError:
            continue
        raise AssertionError(f"{impossible} should not be a length")


def test_a_book_id_without_a_length_leaves_the_length_alone() -> None:
    entry = ShelfEntry(key=key(), title="A", author="B", total_chars=42)
    assert entry.with_book_id("abc").total_chars == 42
