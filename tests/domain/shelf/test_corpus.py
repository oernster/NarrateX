"""The rule that needs the whole library: which half of a filename is the person."""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf import text
from voice_reader.domain.shelf.corpus import (
    MIN_SIGHTINGS,
    author_sightings,
    resolve_author_first,
)
from voice_reader.domain.shelf.identity import ShelfKey, entry_from_filename


def entry(stem: str, suffix: str = ".mobi"):
    key = ShelfKey(path=Path(f"H:/Books/{stem}{suffix}"), size_bytes=1, modified_ns=1)
    return entry_from_filename(key)


def library(*stems: str):
    return tuple(entry(stem) for stem in stems)


GAIMAN = library(
    "American Gods - Neil Gaiman",
    "Anansi Boys - Neil Gaiman",
    "Neverwhere - Neil Gaiman",
    "Neil Gaiman - A Study in Emerald",
)


def test_a_name_behind_several_books_is_counted() -> None:
    assert author_sightings(GAIMAN)[text.name_core("Neil Gaiman")] == 3


def test_a_single_word_name_is_never_counted() -> None:
    entries = library("One - Cussler", "Two - Cussler", "Three - Cussler")
    assert author_sightings(entries) == {}


def test_an_unknown_author_is_never_counted() -> None:
    entries = library("booksreport", "otherreport")
    assert author_sightings(entries) == {}


def test_a_title_naming_a_frequent_author_is_swapped() -> None:
    resolved = resolve_author_first(GAIMAN)
    swapped = resolved[-1]
    assert swapped.title == "A Study in Emerald"
    assert swapped.author == "Neil Gaiman"


def test_the_books_that_were_already_right_are_untouched() -> None:
    resolved = resolve_author_first(GAIMAN)
    assert [e.title for e in resolved[:3]] == [
        "American Gods",
        "Anansi Boys",
        "Neverwhere",
    ]


def test_a_title_matching_an_author_is_left_alone_when_the_author_outweighs_it() -> (
    None
):
    """`The Mediterranean Caper` is a title even though it names an "author"."""

    entries = library(
        "Clive Cussler - Dirk Pitt 02 - The Mediterranean Caper",
        "Clive Cussler - Dirk Pitt 02 - The Mediterranean Caper",
        "Iceberg - Clive Cussler",
        "Inca Gold - Clive Cussler",
        "Night Probe - Clive Cussler",
        "The Mediterranean Caper - Clive Cussler",
    )
    resolved = resolve_author_first(entries)
    assert resolved[-1].title == "The Mediterranean Caper"
    assert resolved[-1].author == "Clive Cussler"


def test_a_duplicated_file_alone_is_not_enough_to_move_anything() -> None:
    """Two sightings is what duplication gives, which is why the floor is three."""

    entries = library("Some Person - A Title", "Some Person - A Title")
    assert MIN_SIGHTINGS > 2
    resolved = resolve_author_first(entries)
    assert resolved[0].title == "Some Person"


def test_an_initial_does_not_hide_an_author_from_the_corpus() -> None:
    entries = library(
        "The Wasp Factory - Iain M. Banks",
        "The Bridge - Iain Banks",
        "Walking on Glass - Iain M Banks",
        "Iain Banks - Against a Dark Background",
    )
    resolved = resolve_author_first(entries)
    assert resolved[-1].title == "Against a Dark Background"
    assert resolved[-1].author == "Iain Banks"


def test_an_empty_library_resolves_to_nothing() -> None:
    assert resolve_author_first(()) == ()


def test_name_core_drops_initials_while_author_key_keeps_them() -> None:
    assert text.name_core("Iain M. Banks") == text.name_core("Iain Banks")
    assert text.author_key("Iain M. Banks") != text.author_key("Iain Banks")
