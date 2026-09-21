"""The two layouts and reading one back from storage."""

from __future__ import annotations

from voice_reader.domain.shelf.layout import DEFAULT_LAYOUT, ShelfLayout, parsed


def test_each_layout_switches_to_the_other() -> None:
    assert ShelfLayout.GRID.other is ShelfLayout.LIST
    assert ShelfLayout.LIST.other is ShelfLayout.GRID


def test_the_shelf_starts_as_a_grid() -> None:
    assert DEFAULT_LAYOUT is ShelfLayout.GRID


def test_a_stored_word_names_its_layout() -> None:
    assert parsed("list") is ShelfLayout.LIST
    assert parsed("grid") is ShelfLayout.GRID


def test_a_word_naming_no_layout_is_none() -> None:
    assert parsed("carousel") is None


def test_something_that_is_not_a_word_is_none() -> None:
    assert parsed(None) is None
    assert parsed(1) is None
