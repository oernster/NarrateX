"""Which narration statuses hold onto the book that is loaded.

One declaration, because three doors ask it: the open control, the shelf and
the loader's own safety net.
"""

from __future__ import annotations

import pytest

from voice_reader.application.dto.narration_state import (
    BOOK_SWITCH_LOCKED,
    NarrationStatus,
    book_switch_locked,
)


@pytest.mark.parametrize(
    "status",
    [
        NarrationStatus.LOADING,
        NarrationStatus.CHUNKING,
        NarrationStatus.SYNTHESIZING,
        NarrationStatus.PLAYING,
    ],
)
def test_the_engine_working_holds_the_book(status: NarrationStatus) -> None:
    assert book_switch_locked(status) is True


@pytest.mark.parametrize(
    "status",
    [
        NarrationStatus.IDLE,
        NarrationStatus.PAUSED,
        NarrationStatus.STOPPED,
        NarrationStatus.ERROR,
    ],
)
def test_the_engine_at_rest_lets_another_book_in(status: NarrationStatus) -> None:
    assert book_switch_locked(status) is False


def test_no_status_at_all_is_not_a_lock() -> None:
    """Absence is an answer: nothing narrating is nothing in the way."""

    assert book_switch_locked(None) is False


def test_every_status_is_ruled_on_one_way_or_the_other() -> None:
    """A status added later cannot slip through unconsidered."""

    settled = BOOK_SWITCH_LOCKED | {
        NarrationStatus.IDLE,
        NarrationStatus.PAUSED,
        NarrationStatus.STOPPED,
        NarrationStatus.ERROR,
    }
    assert settled == set(NarrationStatus)
