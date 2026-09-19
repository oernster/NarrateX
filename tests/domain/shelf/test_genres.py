"""The catalogue, against subject strings measured in the reference library."""

from __future__ import annotations

import pytest

from voice_reader.domain.shelf import genre_catalogue, genres


def test_every_style_hangs_under_a_main_that_exists() -> None:
    for style, main in genre_catalogue.STYLE_PARENT.items():
        assert main in genre_catalogue.MAINS, style


def test_no_name_is_both_a_main_and_a_style() -> None:
    assert not set(genre_catalogue.MAINS) & set(genre_catalogue.STYLE_PARENT)


def test_no_alias_collides_with_another_name() -> None:
    seen: dict[str, str] = {}
    for name, forms in genre_catalogue.ALIASES.items():
        for form in forms:
            assert form not in seen, f"{form} claimed by {seen.get(form)} and {name}"
            seen[form] = name


def test_no_alias_is_also_dropped() -> None:
    dropped = genre_catalogue.SAYS_NOTHING | genre_catalogue.NOT_A_GENRE
    for name, forms in genre_catalogue.ALIASES.items():
        for form in forms:
            assert form not in dropped, f"{form} for {name} is also dropped"


def test_every_alias_is_already_folded() -> None:
    for forms in genre_catalogue.ALIASES.values():
        for form in forms:
            assert genres.fold(form) == form


@pytest.mark.parametrize(
    "spelling",
    [
        "Horror",
        "Horror - General",
        "Fiction - Horror",
        "Horror fiction",
        "Horror tales",
        "Horror stories",
    ],
)
def test_the_six_spellings_of_horror_reach_one_genre(spelling: str) -> None:
    assert genres.read((spelling,)).genres == ("Horror",)


def test_a_style_brings_its_main() -> None:
    reading = genres.read(("Space Opera",))
    assert reading.carries("Space Opera")
    assert reading.carries("Science Fiction")


def test_an_entity_escaped_subject_is_decoded_before_splitting() -> None:
    reading = genres.read(("Mystery &amp; Detective",))
    assert reading.carries("Mystery")
    assert reading.carries("Detective")
    assert reading.carries("Crime")
    assert all("amp" not in name for name in reading.genres)


def test_one_subject_can_state_several_genres() -> None:
    reading = genres.read(("Fiction - Science Fiction; Horror",))
    assert reading.carries("Science Fiction")
    assert reading.carries("Horror")


def test_a_subject_saying_nothing_is_dropped_in_silence() -> None:
    reading = genres.read(("Fiction", "General", "American"))
    assert reading.genres == ()
    assert reading.unmatched == ()


def test_a_provenance_is_dropped_in_silence() -> None:
    reading = genres.read(("Media Tie-In", "Movie"))
    assert reading.genres == ()
    assert reading.unmatched == ()


def test_an_unknown_subject_is_reported_not_discarded() -> None:
    reading = genres.read(("Azizex666",))
    assert reading.genres == ()
    assert reading.unmatched == ("Azizex666",)


def test_an_unknown_subject_is_reported_once() -> None:
    reading = genres.read(("Azizex666", "Azizex666"))
    assert reading.unmatched == ("Azizex666",)


def test_genres_read_in_catalogue_order_whatever_the_file_says() -> None:
    first = genres.read(("Horror", "Science Fiction"))
    second = genres.read(("Science Fiction", "Horror"))
    assert first.genres == second.genres


def test_mains_reports_only_the_mains() -> None:
    reading = genres.read(("Space Opera", "Ghost Stories"))
    assert reading.mains == ("Science Fiction", "Horror")


def test_crime_is_the_main_and_mystery_sits_beneath_it() -> None:
    assert "Crime" in genre_catalogue.MAINS
    assert genre_catalogue.STYLE_PARENT["Mystery"] == "Crime"


def test_criticism_is_a_main_of_its_own() -> None:
    assert "Criticism" in genre_catalogue.MAINS
    assert "Criticism" not in genre_catalogue.STYLE_PARENT


def test_suspense_folds_into_thriller() -> None:
    assert genres.read(("Suspense",)).genres == ("Thriller",)


def test_name_for_answers_the_catalogue_name() -> None:
    assert genres.name_for("Horror tales") == "Horror"
    assert genres.name_for("General") is None
    assert genres.name_for("Azizex666") is None


def test_is_ignorable_tells_the_dropped_from_the_unknown() -> None:
    assert genres.is_ignorable("General")
    assert genres.is_ignorable("Movie")
    assert genres.is_ignorable("   ")
    assert not genres.is_ignorable("Azizex666")


def test_pieces_of_splits_on_every_separator_the_sources_use() -> None:
    assert genres.pieces_of("a;b,c/d&e") == ("a", "b", "c", "d", "e")


def test_with_mains_adds_nothing_for_a_main() -> None:
    assert genres.with_mains(frozenset({"Horror"})) == frozenset({"Horror"})
