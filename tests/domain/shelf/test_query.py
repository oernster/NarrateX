"""What the filter, the search and the three orderings actually mean."""

from __future__ import annotations

from pathlib import Path

from voice_reader.domain.shelf import query as query_rules
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.query import Order, ShelfQuery
from voice_reader.domain.shelf.works import Work


def work(
    title: str,
    author: str,
    *,
    subjects: tuple[str, ...] = (),
    book_id: str | None = None,
) -> Work:
    key = ShelfKey(path=Path(f"H:/{title}.mobi"), size_bytes=1, modified_ns=1)
    entry = ShelfEntry(
        key=key, title=title, author=author, subjects=subjects, book_id=book_id
    )
    return Work(title=title, author=author, entries=(entry,))


HORROR = work("The Shining", "Stephen King", subjects=("Horror",))
SPACE = work("Rama", "Arthur C. Clarke", subjects=("Space Opera",))
PLAIN = work("Untagged", "Zoe Zeta")
ALL = (HORROR, SPACE, PLAIN)


def test_an_empty_query_shows_everything() -> None:
    assert len(query_rules.apply(ALL, ShelfQuery())) == 3


def test_a_tick_shows_that_genre_alone() -> None:
    query = ShelfQuery(genres=frozenset({"Horror"}))
    assert query_rules.apply(ALL, query) == (HORROR,)


def test_every_tick_adds_to_what_is_shown() -> None:
    query = ShelfQuery(genres=frozenset({"Horror", "Science Fiction"}))
    shown = query_rules.apply(ALL, query)
    assert set(shown) == {HORROR, SPACE}


def test_a_main_brings_the_works_carrying_only_its_styles() -> None:
    query = ShelfQuery(genres=frozenset({"Science Fiction"}))
    assert query_rules.apply(ALL, query) == (SPACE,)


def test_works_stating_no_genre_have_a_choice_of_their_own() -> None:
    query = ShelfQuery(include_ungenred=True)
    assert query_rules.apply(ALL, query) == (PLAIN,)


def test_the_no_genre_choice_combines_with_a_tick() -> None:
    query = ShelfQuery(genres=frozenset({"Horror"}), include_ungenred=True)
    assert set(query_rules.apply(ALL, query)) == {HORROR, PLAIN}


def test_clearing_the_filter_shows_everything_again() -> None:
    assert not ShelfQuery().filters_by_genre
    assert len(query_rules.apply(ALL, ShelfQuery())) == 3


def test_a_search_narrows_by_title() -> None:
    assert query_rules.apply(ALL, ShelfQuery(text="shining")) == (HORROR,)


def test_a_search_narrows_by_author() -> None:
    assert query_rules.apply(ALL, ShelfQuery(text="clarke")) == (SPACE,)


def test_a_search_ignores_punctuation_and_case() -> None:
    assert query_rules.apply(ALL, ShelfQuery(text="ARTHUR C CLARKE")) == (SPACE,)


def test_a_search_of_punctuation_alone_narrows_nothing() -> None:
    assert len(query_rules.apply(ALL, ShelfQuery(text="!!!"))) == 3


def test_a_search_of_spaces_alone_narrows_nothing() -> None:
    assert len(query_rules.apply(ALL, ShelfQuery(text="   "))) == 3


def test_a_search_and_a_filter_both_apply() -> None:
    query = ShelfQuery(genres=frozenset({"Horror"}), text="rama")
    assert query_rules.apply(ALL, query) == ()


def test_the_default_order_is_author_then_title() -> None:
    shown = query_rules.apply(ALL, ShelfQuery())
    assert [w.author for w in shown] == [
        "Arthur C. Clarke",
        "Stephen King",
        "Zoe Zeta",
    ]


def test_ordering_by_title_ignores_the_author() -> None:
    shown = query_rules.apply(ALL, ShelfQuery(order=Order.TITLE))
    assert [w.title for w in shown] == ["Rama", "The Shining", "Untagged"]


def test_ordering_by_most_recently_read_puts_the_last_one_first() -> None:
    read_first = work("One", "A Author", book_id="one")
    read_last = work("Two", "B Author", book_id="two")
    never = work("Three", "C Author")
    shown = query_rules.apply(
        (read_first, read_last, never),
        ShelfQuery(order=Order.RECENTLY_READ),
        recency={"one": 1, "two": 2},
    )
    assert [w.title for w in shown] == ["Two", "One", "Three"]


def test_recently_read_with_nothing_read_falls_back_to_the_default_order() -> None:
    shown = query_rules.apply(ALL, ShelfQuery(order=Order.RECENTLY_READ))
    assert [w.author for w in shown] == [
        "Arthur C. Clarke",
        "Stephen King",
        "Zoe Zeta",
    ]


def test_genre_counts_count_styles_and_their_mains() -> None:
    counts = query_rules.genre_counts(ALL)
    assert counts["Horror"] == 1
    assert counts["Science Fiction"] == 1
    assert counts["Space Opera"] == 1
    assert "Untagged" not in counts


def test_the_no_genre_count_is_reported_separately() -> None:
    assert query_rules.ungenred_count(ALL) == 1
