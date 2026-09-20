"""Which folders the shelf watches; what a walk of them answers."""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf import roots
from voice_reader.domain.shelf.discovery import FileMetadata, WalkResult
from voice_reader.domain.shelf.identity import ShelfKey

BOOKS = Path("H:/Books")
INSIDE = Path("H:/Books/FIXED/uncatalogued")
ELSEWHERE = Path("D:/Other")


def test_a_trailing_separator_does_not_make_a_second_root() -> None:
    assert roots.normalised(Path("H:/Books/")) == roots.normalised(BOOKS)


def test_a_root_contains_itself() -> None:
    assert roots.contains(BOOKS, BOOKS)


def test_a_root_contains_what_sits_beneath_it() -> None:
    assert roots.contains(BOOKS, INSIDE)


def test_a_root_contains_nothing_outside_it() -> None:
    assert not roots.contains(BOOKS, ELSEWHERE)


def test_a_folder_inside_an_existing_root_is_already_covered() -> None:
    assert roots.covering((BOOKS,), INSIDE) == BOOKS


def test_a_folder_outside_every_root_is_covered_by_none() -> None:
    assert roots.covering((BOOKS,), ELSEWHERE) is None


def test_adding_a_covered_folder_changes_nothing() -> None:
    assert roots.added((BOOKS,), INSIDE) == (BOOKS,)


def test_adding_a_folder_that_swallows_a_root_replaces_it() -> None:
    assert roots.covered_by((INSIDE,), BOOKS) == (INSIDE,)
    assert roots.added((INSIDE,), BOOKS) == (roots.normalised(BOOKS),)


def test_adding_a_folder_elsewhere_keeps_both() -> None:
    assert roots.added((BOOKS,), ELSEWHERE) == (BOOKS, roots.normalised(ELSEWHERE))


def test_removing_a_root_compares_the_settled_spelling() -> None:
    assert roots.removed((BOOKS, ELSEWHERE), Path("H:/Books/")) == (ELSEWHERE,)


def test_removing_a_root_that_was_never_there_changes_nothing() -> None:
    assert roots.removed((BOOKS,), ELSEWHERE) == (BOOKS,)


def key(name: str) -> ShelfKey:
    return ShelfKey(path=Path(f"H:/Books/{name}"), size_bytes=1, modified_ns=1)


def test_an_empty_walk_found_nothing_and_faulted_on_nothing() -> None:
    walk = WalkResult()
    assert (walk.found, walk.faults, walk.root_reachable) == (0, 0, True)


def test_two_walks_read_as_one() -> None:
    first = WalkResult(keys=(key("a.mobi"),), unreadable=(Path("H:/Books/locked"),))
    second = WalkResult(keys=(key("b.mobi"),), root_reachable=False)
    joined = first.joined_with(second)
    assert joined.found == 2
    assert joined.faults == 1
    assert not joined.root_reachable


def test_metadata_states_nothing_by_default() -> None:
    empty = FileMetadata()
    assert not empty.states_a_title
    assert not empty.states_an_author
    assert empty.subjects == ()
    assert not empty.has_cover


def test_whitespace_is_not_a_statement() -> None:
    blank = FileMetadata(title="  ", author="\t")
    assert not blank.states_a_title
    assert not blank.states_an_author


def test_metadata_reports_what_it_holds() -> None:
    stated = FileMetadata(title="Rama", author="Clarke", subjects=("Science Fiction",))
    assert stated.states_a_title
    assert stated.states_an_author
    assert stated.subjects == ("Science Fiction",)
