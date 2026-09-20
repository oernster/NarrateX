"""The catalogue as tick boxes, plus the two questions it answers."""

from __future__ import annotations

from voice_reader.domain.shelf.genre_catalogue import CATALOGUE, NAMES
from voice_reader.ui.genre_grid import (
    ASKING,
    STATING,
    GenreGrid,
    dealt_into_columns,
    mnemonic_safe,
)


def test_every_genre_in_the_catalogue_gets_a_box(qapp) -> None:
    del qapp
    grid = GenreGrid()

    assert set(grid.boxes) == set(NAMES)


def test_the_groups_are_dealt_by_height_not_in_order() -> None:
    """Crime carries seven styles while nine mains carry none."""

    columns = dealt_into_columns(CATALOGUE, 3)
    heights = [sum(1 + len(styles) for _main, styles in col) for col in columns]

    assert len(columns) == 3
    assert max(heights) - min(heights) <= max(
        1 + len(styles) for _main, styles in CATALOGUE
    )
    dealt = [main for col in columns for main, _styles in col]
    assert sorted(dealt) == sorted(main for main, _styles in CATALOGUE)


def test_an_ampersand_is_asked_for_literally() -> None:
    """Qt reads a single ampersand as the marker before a shortcut key."""

    assert mnemonic_safe("Drum & Bass") == "Drum && Bass"


def test_stating_a_style_states_its_main(qapp) -> None:
    """A book marked Space Opera IS science fiction (FR-BS-046)."""

    del qapp
    grid = GenreGrid(manner=STATING)

    grid.boxes["Space Opera"].setChecked(True)

    assert grid.chosen() == ("Science Fiction", "Space Opera")


def test_clearing_a_main_clears_its_styles(qapp) -> None:
    del qapp
    grid = GenreGrid(manner=STATING)
    grid.boxes["Space Opera"].setChecked(True)

    grid.boxes["Science Fiction"].setChecked(False)

    assert grid.chosen() == ()


def test_clearing_a_style_leaves_its_main_alone(qapp) -> None:
    """A book may still be science fiction after it stops being space opera."""

    del qapp
    grid = GenreGrid(manner=STATING)
    grid.boxes["Space Opera"].setChecked(True)

    grid.boxes["Space Opera"].setChecked(False)

    assert grid.chosen() == ("Science Fiction",)


def test_asking_for_a_style_asks_for_that_style_alone(qapp) -> None:
    """Ticking Space Opera is not asking for every kind of science fiction."""

    del qapp
    grid = GenreGrid(manner=ASKING)

    grid.boxes["Space Opera"].setChecked(True)

    assert grid.chosen() == ("Space Opera",)


def test_asking_never_clears_on_the_readers_behalf(qapp) -> None:
    del qapp
    grid = GenreGrid(("Science Fiction", "Space Opera"), manner=ASKING)

    grid.boxes["Science Fiction"].setChecked(False)

    assert grid.chosen() == ("Space Opera",)


def test_what_is_ticked_reads_in_catalogue_order(qapp) -> None:
    """The boxes are built column by column, which is not the reading order."""

    del qapp
    grid = GenreGrid(("Western", "Horror", "Science Fiction"), manner=ASKING)

    assert grid.chosen() == ("Science Fiction", "Horror", "Western")


def test_the_whole_grid_clears_in_one_go(qapp) -> None:
    del qapp
    grid = GenreGrid(("Horror", "Western"), manner=ASKING)

    grid.set_all(False)

    assert grid.chosen() == ()


def test_the_hint_says_which_question_is_being_asked(qapp) -> None:
    """Ticking widens what is shown; or it describes a book. Never both."""

    del qapp
    from PySide6.QtWidgets import QLabel

    asking = GenreGrid(manner=ASKING).findChild(QLabel)
    stating = GenreGrid(manner=STATING).findChild(QLabel)

    assert asking.text() == ASKING.hint
    assert stating.text() == STATING.hint
    assert ASKING.hint != STATING.hint
