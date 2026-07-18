"""Translate between Python string indices and Qt cursor positions.

Qt stores text as UTF-16, so a `QTextCursor` position counts *code units*. A
Python string index counts *code points*. The two agree until the text contains
a character outside the Basic Multilingual Plane, such as an emoji, which Qt
counts as two positions and Python counts as one.

From that character onwards every offset is out by one, and by one more for
each further non-BMP character. Highlighting drifts silently, further into the
book the more of them there are, which is exactly the kind of fault that never
shows up in a fixture and always shows up in a real book.

Both directions are precomputed once per document so translation stays cheap
enough to run on every playback tick.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

# Characters above this take two UTF-16 code units (a surrogate pair).
_MAX_SINGLE_UNIT_CODEPOINT = 0xFFFF


@dataclass(frozen=True, slots=True)
class Utf16PositionMap:
    """Maps Python indices to Qt positions for one fixed piece of text."""

    # Python indices of the characters needing a surrogate pair, ascending.
    wide_indices: tuple[int, ...]
    # Qt position of each of those characters, ascending.
    wide_positions: tuple[int, ...]

    @classmethod
    def for_text(cls, text: str) -> "Utf16PositionMap":
        wide = tuple(
            index
            for index, char in enumerate(text)
            if ord(char) > _MAX_SINGLE_UNIT_CODEPOINT
        )
        # The nth such character sits n positions later than its index.
        positions = tuple(index + rank for rank, index in enumerate(wide))
        return cls(wide_indices=wide, wide_positions=positions)

    @property
    def is_identity(self) -> bool:
        """Whether the two coordinate spaces coincide, as they usually do."""

        return not self.wide_indices

    def to_qt(self, index: int) -> int:
        """Qt cursor position for a Python string index."""

        if self.is_identity:
            return index
        return index + bisect_left(self.wide_indices, index)

    def to_index(self, position: int) -> int:
        """Python string index for a Qt cursor position."""

        if self.is_identity:
            return position
        return position - bisect_left(self.wide_positions, position)
