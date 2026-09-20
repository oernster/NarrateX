"""The shelf a scan still running can already draw (FR-BS-036).

Kept apart from `test_library.py` because these ask a different question of the
same service: not what the index holds; what a part of a walk folds to
before anything has been saved.
"""

from __future__ import annotations

from voice_reader.domain.shelf.corpus import MIN_SIGHTINGS
from voice_reader.domain.shelf.query import ShelfQuery

from tests.application.shelf.test_library import RAMA, SHINING, entry, library


def test_a_part_of_a_walk_folds_to_the_works_it_holds() -> None:
    shelf, _, _ = library()

    drawn = shelf.works_so_far((SHINING, RAMA))

    assert {work.title for work in drawn} == {"The Shining", "Rama"}


def test_nothing_walked_yet_is_an_empty_shelf() -> None:
    shelf, _, _ = library()

    assert shelf.works_so_far(()) == ()


def test_the_index_is_not_read_for_the_works() -> None:
    """The entries in hand are the shelf; what was saved before is not."""

    shelf, _, _ = library(entries=(SHINING,))

    drawn = shelf.works_so_far((RAMA,))

    assert [work.title for work in drawn] == ["Rama"]


def test_what_the_reader_stated_is_carried_onto_a_filling_shelf() -> None:
    unstated, _, _ = library()
    token = unstated.works_so_far((SHINING,))[0].token
    shelf, _, _ = library(stated={token: ("Horror",)})

    drawn = shelf.works_so_far((SHINING,))

    assert drawn[0].genres == ("Horror",)


def test_a_partial_corpus_still_puts_an_author_first_name_right() -> None:
    """The rule the scanner applies on save is applied here too.

    Without it a shelf filling in front of the reader would show a work titled
    `Kurt Vonnegut` by `Bluebeard` until the scan ended and put it right.
    """

    weight = tuple(
        entry(f"H:/Books/right-{number}.mobi", f"Novel {number}", "Kurt Vonnegut")
        for number in range(MIN_SIGHTINGS)
    )
    reversed_pair = entry("H:/Books/wrong.mobi", "Kurt Vonnegut", "Bluebeard")
    shelf, _, _ = library()

    drawn = shelf.works_so_far(weight + (reversed_pair,))

    put_right = next(work for work in drawn if work.title == "Bluebeard")
    assert put_right.author == "Kurt Vonnegut"


def test_a_query_narrows_works_already_in_hand() -> None:
    shelf, _, _ = library()
    held = shelf.works_so_far((SHINING, RAMA))

    shown = shelf.view_of(held, ShelfQuery(genres=("Horror",)))

    assert [work.title for work in shown] == ["The Shining"]


def test_the_same_question_is_asked_of_a_saved_shelf() -> None:
    """One way to apply a query, whether the works were saved or just walked."""

    shelf, _, _ = library(entries=(SHINING, RAMA))

    query = ShelfQuery(genres=("Horror",))
    assert shelf.view_of(shelf.works(), query) == shelf.view_of(
        shelf.works_so_far((SHINING, RAMA)), query
    )
