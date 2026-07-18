"""Say where the listener is, in terms of the book rather than the machine.

The status line used to count text fragments: "1847/3200". Those are the pieces
the narrator hands to the speech engine one at a time, so the number is an
implementation detail that happens to be visible. It answers no question a
listener has, and on a long book it counts into the thousands.

What a listener wants to know is which chapter they are in and how much of it
is left, so that is what this produces.

Everything here works in book character offsets. Those are the coordinates the
chapter anchors, the bookmarks and the resume position already share, so the
label cannot drift out of step with the position it describes. Counting
fragments instead would mean reconciling two different index spaces, one of
which skips the fragments that turn out to have nothing to say.
"""

from __future__ import annotations

from typing import Sequence

from voice_reader.domain.entities.chapter import Chapter

_PERCENT = 100

# A chapter is never reported as finished while it is still being read, and
# never as unstarted once it has been entered. The label is a reassurance that
# something is happening, so it should not sit at either extreme.
_MIN_SHOWN_PCT = 1
_MAX_SHOWN_PCT = 99


def _current_index(chapters: Sequence[Chapter], char_offset: int) -> int | None:
    current: int | None = None
    for index, chapter in enumerate(chapters):
        if int(chapter.char_offset) <= int(char_offset):
            current = index
        else:
            break
    return current


def chapter_progress_label(
    chapters: Sequence[Chapter],
    *,
    char_offset: int | None,
    book_length: int,
) -> str | None:
    """Return "Prologue - 34%", or None when there is nothing to say.

    None means the caller should keep whatever it was showing: before playback
    starts, or for a book with no chapters, there is no honest answer and an
    invented one would be worse than the previous label.
    """

    if char_offset is None or not chapters:
        return None

    index = _current_index(chapters, int(char_offset))
    if index is None:
        return None

    chapter = chapters[index]
    start = int(chapter.char_offset)

    # A chapter runs until the next one starts, or until the end of the book.
    following = index + 1
    end = (
        int(chapters[following].char_offset)
        if following < len(chapters)
        else int(book_length)
    )

    span = end - start
    if span <= 0:
        return str(chapter.title)

    travelled = max(0, min(int(char_offset) - start, span))
    pct = int(travelled * _PERCENT / span)
    pct = max(_MIN_SHOWN_PCT, min(_MAX_SHOWN_PCT, pct))

    return f"{chapter.title} - {pct}%"
