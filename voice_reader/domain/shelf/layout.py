"""How the shelf is drawn: tiles or rows (FR-BS-050, FR-BS-051 and FR-BS-052).

A value rather than a flag, because it is stored between runs: a boolean named
"list" is readable only by somebody who remembers which way round it was, while
a stored word says what it is.
"""

from __future__ import annotations

from enum import Enum


class ShelfLayout(Enum):
    """The two ways the shelf lays its works out."""

    GRID = "grid"
    LIST = "list"

    @property
    def other(self) -> ShelfLayout:
        """The layout a single press switches to."""

        return ShelfLayout.LIST if self is ShelfLayout.GRID else ShelfLayout.GRID


# What a shelf opens in when nothing has been chosen yet. The grid is the
# shelf's own face (FR-BS-050); the list is the alternative a reader asks for.
DEFAULT_LAYOUT = ShelfLayout.GRID


def parsed(stored: object) -> ShelfLayout | None:
    """The layout a stored value names; None when it names none.

    Absence and garbage both answer None rather than raising, since a
    preferences file edited by hand or written by an older build is an ordinary
    thing to meet, not a fault.
    """

    if not isinstance(stored, str):
        return None
    for layout in ShelfLayout:
        if layout.value == stored:
            return layout
    return None
