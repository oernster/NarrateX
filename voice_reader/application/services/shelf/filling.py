"""Pacing the shelf while a scan fills it.

FR-BS-036. The scanner settles one entry at a time while the shelf is drawn
from all of them at once, so something has to decide how often "all of them so
far" is worth handing over. That decision lives here rather than in the window:
it is a rule about pacing, it touches no widget and it is therefore drivable
with a fake clock and no Qt at all.

**Two gates; both have to open.** A count alone paces a slow scan well then
floods a fast one: measured, the reference library settles 2819 entries in as
little as 1.1 seconds once the operating system has the folders cached, which
is twenty-eight redraws of a growing shelf inside a second. A clock alone paces
a fast scan well then leaves a slow one motionless, since a root on a sleeping
drive can go seconds between entries. Asking for both gives roughly four
redraws a second whatever the disk is doing.

**The first handover answers to the count alone.** It is the one that replaces
the words saying the folders are being read with the books themselves, so it
happens as soon as there is a shelf worth showing rather than a quarter of a
second later.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from voice_reader.domain.shelf.identity import ShelfEntry

# How many entries settle between one handover and the next. A hundred tiles is
# several screenfuls, so a shelf that grows by less than that between redraws
# is paying for a fold nobody can see.
ENTRIES_BETWEEN_DRAWS = 100

# The shortest gap between two handovers. Four a second reads as filling rather
# than as flickering; it holds the Qt thread's share of the scan down to
# something a reader can still scroll through.
SECONDS_BETWEEN_DRAWS = 0.25


class ShelfFilling:
    """Accumulates settled entries; says when the shelf is worth redrawing."""

    __slots__ = ("_clock", "_entries", "_since_draw", "_last_draw")

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: list[ShelfEntry] = []
        self._since_draw = 0
        self._last_draw: float | None = None

    def record(self, entry: ShelfEntry) -> tuple[ShelfEntry, ...] | None:
        """Take one settled entry; answer the shelf to draw when one is due.

        None is the ordinary answer and means only that nothing is due yet, so
        a caller that ignores it has ignored nothing. The answer is a snapshot
        rather than the running list, because the caller hands it to another
        thread while this one carries on appending to it.
        """

        self._entries.append(entry)
        self._since_draw += 1
        if self._since_draw < ENTRIES_BETWEEN_DRAWS:
            return None
        now = self._clock()
        if (
            self._last_draw is not None
            and now - self._last_draw < SECONDS_BETWEEN_DRAWS
        ):
            return None
        self._last_draw = now
        self._since_draw = 0
        return tuple(self._entries)
