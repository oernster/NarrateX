"""Reading state on a tile; also the one declaration of what a book file is."""

from __future__ import annotations

import pytest

from voice_reader.domain.shelf import formats, progress
from voice_reader.domain.shelf.progress import ReadingState


def test_a_work_never_opened_is_unread() -> None:
    assert progress.of(None).state is ReadingState.UNREAD
    assert progress.of(None).fraction == 0.0


@pytest.mark.parametrize(
    ("fraction", "state"),
    [
        (0.0, ReadingState.UNREAD),
        (0.004, ReadingState.UNREAD),
        (0.5, ReadingState.READING),
        (0.98, ReadingState.READING),
        (0.995, ReadingState.FINISHED),
        (1.0, ReadingState.FINISHED),
    ],
)
def test_the_state_a_fraction_states(fraction: float, state: ReadingState) -> None:
    assert progress.of(fraction).state is state


@pytest.mark.parametrize(("given", "expected"), [(-3.0, 0.0), (7.0, 1.0)])
def test_a_fraction_outside_the_range_is_bounded(given: float, expected: float) -> None:
    assert progress.of(given).fraction == expected


def test_a_progress_refuses_an_impossible_fraction() -> None:
    with pytest.raises(ValueError):
        progress.Progress(state=ReadingState.READING, fraction=1.5)


def test_percent_reads_as_a_whole_number() -> None:
    assert progress.of(0.5).percent == 50
    assert progress.of(0.666).percent == 67


def test_every_format_the_open_control_offers_is_recognised() -> None:
    offered = {
        ".epub",
        ".pdf",
        ".txt",
        ".md",
        ".markdown",
        ".mobi",
        ".azw",
        ".azw3",
        ".prc",
        ".kfx",
    }
    assert formats.RECOGNISED == offered


def test_every_recognised_format_has_a_place_in_the_preference() -> None:
    assert set(formats.PREFERENCE) == formats.RECOGNISED
    assert len(formats.PREFERENCE) == len(formats.RECOGNISED)


def test_a_native_format_is_preferred_to_a_kindle_one() -> None:
    for native in formats.NATIVE:
        for kindle in formats.KINDLE:
            assert formats.preference_rank(native) < formats.preference_rank(kindle)


def test_an_unrecognised_format_sorts_last() -> None:
    assert formats.preference_rank(".zip") == len(formats.PREFERENCE)


def test_is_book_ignores_case() -> None:
    assert formats.is_book(".EPUB")
    assert not formats.is_book(".zip")


def test_only_kindle_formats_need_a_conversion() -> None:
    assert formats.needs_conversion(".MOBI")
    assert not formats.needs_conversion(".epub")


def test_kfx_is_not_a_palm_container() -> None:
    assert not formats.reads_palm_container(".kfx")
    assert formats.reads_palm_container(".AZW3")


def test_the_dialog_filter_is_derived_from_the_one_list() -> None:
    written = formats.dialog_filter()
    for suffix in formats.RECOGNISED:
        assert "*" + suffix in written
    assert written.endswith(";;All Files (*)")
