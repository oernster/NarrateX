"""Folding entries into works, against the duplication the library actually holds."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.works import Work, gather, possible_duplicates


def entry(
    path: str,
    title: str,
    author: str,
    *,
    subjects: tuple[str, ...] = (),
    book_id: str | None = None,
    has_cover: bool = False,
) -> ShelfEntry:
    return ShelfEntry(
        key=ShelfKey(path=Path(path), size_bytes=1, modified_ns=1),
        title=title,
        author=author,
        subjects=subjects,
        book_id=book_id,
        has_cover=has_cover,
    )


MOBI = entry(
    "H:/Books/uncatalogued/2001_ A Space Odyssey - Arthur C. Clarke.mobi",
    "2001: A Space Odyssey",
    "Arthur C. Clarke",
)
AZW3 = entry(
    "H:/Books/FIXED/uncatalogued/2001_ A Space Odyssey - Arthur C. Clarke.azw3",
    "2001: A Space Odyssey",
    "Arthur C. Clarke",
)


def test_the_same_book_in_two_formats_is_one_work() -> None:
    works = gather((MOBI, AZW3))
    assert len(works) == 1
    assert works[0].formats == (".azw3", ".mobi")


def test_a_work_opens_its_cheapest_format() -> None:
    epub = entry("H:/Books/x.epub", "2001: A Space Odyssey", "Arthur C. Clarke")
    works = gather((MOBI, AZW3, epub))
    assert works[0].preferred.suffix == ".epub"


def test_the_cheapest_of_two_kindle_formats_is_the_azw3() -> None:
    assert gather((MOBI, AZW3))[0].preferred.suffix == ".azw3"


def test_a_tie_breaks_on_the_path_not_on_the_walk_order() -> None:
    first = entry("H:/Books/b.mobi", "One", "A")
    second = entry("H:/Books/a.mobi", "One", "A")
    assert gather((first, second))[0].preferred.key.path == Path("H:/Books/a.mobi")
    assert gather((second, first))[0].preferred.key.path == Path("H:/Books/a.mobi")


def test_a_work_needs_an_entry() -> None:
    with pytest.raises(ValueError):
        Work(title="One", author="A", entries=())


def test_a_work_reports_the_first_book_id_any_entry_holds() -> None:
    known = entry("H:/Books/a.mobi", "One", "A", book_id="abc")
    unknown = entry("H:/Books/a.azw3", "One", "A")
    assert gather((known, unknown))[0].book_id == "abc"


def test_a_work_with_no_book_id_reports_none() -> None:
    assert gather((MOBI,))[0].book_id is None


def test_a_work_has_a_cover_when_any_entry_does() -> None:
    plain = entry("H:/Books/a.mobi", "One", "A")
    covered = entry("H:/Books/a.azw3", "One", "A", has_cover=True)
    assert gather((plain, covered))[0].has_cover
    assert not gather((plain,))[0].has_cover


def test_a_work_carries_the_genres_of_every_entry() -> None:
    first = entry("H:/Books/a.mobi", "One", "A", subjects=("Horror",))
    second = entry("H:/Books/a.azw3", "One", "A", subjects=("Space Opera",))
    work = gather((first, second))[0]
    assert work.carries("Horror")
    assert work.carries("Science Fiction")


def test_a_reader_statement_replaces_what_the_file_said() -> None:
    work = Work(
        title="One",
        author="A",
        entries=(entry("H:/Books/a.mobi", "One", "A", subjects=("Horror",)),),
        stated_genres=("Space Opera",),
    )
    assert work.carries("Space Opera")
    assert work.carries("Science Fiction")
    assert not work.carries("Horror")


def test_works_come_back_ordered_by_author_then_title() -> None:
    clarke = entry("H:/Books/a.mobi", "Rama", "Arthur C. Clarke")
    koontz = entry("H:/Books/b.mobi", "Anti-Man", "Dean R. Koontz")
    assert [work.author for work in gather((koontz, clarke))] == [
        "Arthur C. Clarke",
        "Dean R. Koontz",
    ]


def test_a_work_shows_the_spelling_of_the_file_it_will_open() -> None:
    kindle = entry("H:/Books/a.mobi", "Stand, The", "Stephen King")
    native = entry("H:/Books/a.epub", "The Stand", "Stephen King")
    assert gather((kindle, native))[0].title == "The Stand"


def test_a_subtitle_added_to_one_copy_is_marked_not_merged() -> None:
    plain = entry("H:/Books/a.mobi", "The Stand", "Stephen King")
    longer = entry("H:/Books/b.mobi", "The Stand Complete and Uncut", "Stephen King")
    works = gather((plain, longer))
    assert len(works) == 2
    assert len(possible_duplicates(works)) == 1


def test_a_misspelling_is_not_marked_which_is_the_stated_limit() -> None:
    right = entry("H:/Books/a.mobi", "The Acquitaine Progression", "Robert Ludlum")
    wrong = entry("H:/Books/b.mobi", "Aquaintaine Progession, The", "Robert Ludlum")
    assert possible_duplicates(gather((right, wrong))) == frozenset()


def test_different_authors_are_never_marked() -> None:
    first = entry("H:/Books/a.mobi", "The Stand", "Stephen King")
    second = entry("H:/Books/b.mobi", "The Stand Complete", "Someone Else")
    assert possible_duplicates(gather((first, second))) == frozenset()


def test_a_title_that_folds_to_nothing_is_never_marked() -> None:
    first = Work(title="!", author="A", entries=(entry("H:/a.mobi", "!", "A"),))
    second = Work(
        title="! more", author="A", entries=(entry("H:/b.mobi", "! more", "A"),)
    )
    assert possible_duplicates((first, second)) == frozenset()


def test_one_work_alone_is_never_marked() -> None:
    assert possible_duplicates(gather((MOBI,))) == frozenset()
