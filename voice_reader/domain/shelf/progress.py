"""How far through a book the reader is, as a tile states it.

FR-BS-054: a tile shows a state of unread, reading or finished, together with a
bar. The state is derived here rather than stored, because NarrateX already
keeps the only fact involved, which is the resume position; a second store of
"finished" would be a second truth able to disagree with the first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Narration resumes at a chunk boundary, so a book listened to the end settles
# a little short of its last character rather than exactly on it. Anything past
# this reads as finished.
FINISHED_FRACTION = 0.99

# Below this a book has been opened but barely touched, which is still unread
# to a reader looking at a shelf.
STARTED_FRACTION = 0.005


class ReadingState(Enum):
    UNREAD = "unread"
    READING = "reading"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class Progress:
    """A work's reading progress, for one tile."""

    state: ReadingState
    fraction: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError("progress fraction must lie between 0 and 1")

    @property
    def percent(self) -> int:
        return int(round(self.fraction * 100))


UNREAD = Progress(state=ReadingState.UNREAD, fraction=0.0)


def of(fraction: float | None) -> Progress:
    """The progress a fraction states; unread when there is no fraction.

    A work never opened has no fraction at all, which is not the same as a
    fraction of zero; both read as unread, so the distinction costs the reader
    nothing while keeping the absence honest.
    """

    if fraction is None:
        return UNREAD
    bounded = min(max(float(fraction), 0.0), 1.0)
    if bounded >= FINISHED_FRACTION:
        return Progress(state=ReadingState.FINISHED, fraction=bounded)
    if bounded <= STARTED_FRACTION:
        return Progress(state=ReadingState.UNREAD, fraction=bounded)
    return Progress(state=ReadingState.READING, fraction=bounded)
