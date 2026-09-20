"""How often a scan in progress hands the shelf over (FR-BS-036).

Driven with a clock that only moves when a test moves it, so nothing here waits
on real time and nothing here can pass or fail by being run on a fast machine.
"""

from __future__ import annotations

from pathlib import Path

from voice_reader.application.services.shelf.filling import (
    ENTRIES_BETWEEN_DRAWS,
    SECONDS_BETWEEN_DRAWS,
    ShelfFilling,
)
from voice_reader.domain.shelf.identity import ShelfEntry

from tests.application.shelf.shelf_fakes import key


class _Clock:
    """A clock standing still until a test says otherwise."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def entry(number: int) -> ShelfEntry:
    return ShelfEntry(
        key=key(f"H:/Books/{number}.mobi"),
        title=f"Book {number}",
        author="Stephen King",
    )


def feed(filling: ShelfFilling, count: int, *, start: int = 0) -> list[tuple]:
    """Record `count` entries; answer every batch that came back."""

    drawn = []
    for number in range(start, start + count):
        ready = filling.record(entry(number))
        if ready is not None:
            drawn.append(ready)
    return drawn


def test_nothing_is_drawn_before_the_count_is_reached() -> None:
    filling = ShelfFilling(clock=_Clock())

    assert feed(filling, ENTRIES_BETWEEN_DRAWS - 1) == []


def test_the_first_batch_arrives_on_the_count_alone() -> None:
    """The clock has not moved at all, which is the fast-scan case."""

    filling = ShelfFilling(clock=_Clock())

    drawn = feed(filling, ENTRIES_BETWEEN_DRAWS)

    assert len(drawn) == 1
    assert len(drawn[0]) == ENTRIES_BETWEEN_DRAWS


def test_a_batch_is_every_entry_so_far_not_only_the_new_ones() -> None:
    """The shelf is drawn from the whole corpus, so the whole corpus goes."""

    clock = _Clock()
    filling = ShelfFilling(clock=clock)
    feed(filling, ENTRIES_BETWEEN_DRAWS)
    clock.now += SECONDS_BETWEEN_DRAWS

    drawn = feed(filling, ENTRIES_BETWEEN_DRAWS, start=ENTRIES_BETWEEN_DRAWS)

    assert len(drawn) == 1
    assert len(drawn[0]) == ENTRIES_BETWEEN_DRAWS * 2


def test_a_second_batch_waits_for_the_clock() -> None:
    """A thousand entries inside one tick is one redraw, not ten."""

    filling = ShelfFilling(clock=_Clock())

    drawn = feed(filling, ENTRIES_BETWEEN_DRAWS * 10)

    assert len(drawn) == 1


def test_the_batch_held_back_by_the_clock_goes_the_moment_it_opens() -> None:
    """Held back is not dropped: the entries that waited are in the batch."""

    clock = _Clock()
    filling = ShelfFilling(clock=clock)
    feed(filling, ENTRIES_BETWEEN_DRAWS * 2)
    clock.now += SECONDS_BETWEEN_DRAWS

    drawn = feed(filling, 1, start=ENTRIES_BETWEEN_DRAWS * 2)

    assert len(drawn) == 1
    assert len(drawn[0]) == ENTRIES_BETWEEN_DRAWS * 2 + 1


def test_the_clock_gate_is_shut_a_hair_under_the_gap() -> None:
    clock = _Clock()
    filling = ShelfFilling(clock=clock)
    feed(filling, ENTRIES_BETWEEN_DRAWS)
    clock.now += SECONDS_BETWEEN_DRAWS / 2

    assert feed(filling, ENTRIES_BETWEEN_DRAWS, start=ENTRIES_BETWEEN_DRAWS) == []


def test_the_default_clock_is_the_real_one() -> None:
    """No clock passed is the production case; it still paces by the count."""

    filling = ShelfFilling()

    assert len(feed(filling, ENTRIES_BETWEEN_DRAWS)) == 1


def test_the_entries_answered_are_the_ones_recorded() -> None:
    filling = ShelfFilling(clock=_Clock())

    drawn = feed(filling, ENTRIES_BETWEEN_DRAWS)

    assert drawn[0][0].key.path == Path("H:/Books/0.mobi")
    assert drawn[0][-1].title == f"Book {ENTRIES_BETWEEN_DRAWS - 1}"
