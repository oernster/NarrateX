"""Compare extracted text against the canonical source text.

Two parts of the app need to find a piece of text inside `normalized_text` and
report exactly where it sits: anchoring, which locates a format reader's blocks,
and narration planning, which locates the chunks handed to the TTS engine.

Both face the same mismatch. Text arrives wrapped, spaced and hyphenated as its
producer left it, while `normalized_text` has already been rewritten. Comparing
literally loses the match; comparing loosely corrupts the offsets. So matching
ignores whitespace entirely and folds the few characters the extraction
rewrites, while every kept character carries its true offset alongside.

Each fold is one character wide or dropped outright, so the offsets stay true
to the original text. That property is what lets a caller report a span into
the untouched source after matching on the folded form.
"""

from __future__ import annotations

# Characters the extraction removes outright, so text still carrying one would
# never be found. The soft hyphen is invisible typesetting advice.
_DROPPED_IN_SOURCE = frozenset({"­"})

# Characters the extraction rewrites, mapped to what it rewrites them to. The
# non-breaking hyphen becomes a plain one, which is what a hyphenated term in a
# typeset PDF hinges on.
_FOLDED_IN_SOURCE = {"‑": "-"}


def _fold_char(char: str) -> str | None:
    """Fold one character for matching, or None when it carries no meaning."""

    if char.isspace() or char in _DROPPED_IN_SOURCE:
        return None
    return _FOLDED_IN_SOURCE.get(char, char)


def condense(text: str) -> tuple[str, tuple[int, ...]]:
    """Return `text` folded for matching, plus each kept character's offset."""

    condensed: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        folded = _fold_char(char)
        if folded is None:
            continue
        condensed.append(folded)
        offsets.append(index)
    return "".join(condensed), tuple(offsets)


def match_key(text: str) -> str:
    """Fold a fragment the same way, so the two can be compared."""

    return "".join(
        folded for folded in (_fold_char(char) for char in text) if folded is not None
    )


def locate(
    *,
    condensed: str,
    offsets: tuple[int, ...],
    needle: str,
    cursor: int = 0,
) -> tuple[int, int, int] | None:
    """Find `needle` at or after `cursor`, as (start, end, next_cursor).

    The span returned indexes the original text the condensed form came from.
    Searching forward from a cursor keeps repeated text, a running header on
    every page, matched to the right occurrence. A fragment that cannot be
    found returns None rather than a guess.
    """

    if not needle:
        return None

    found = condensed.find(needle, cursor)
    if found < 0:
        return None

    last = found + len(needle) - 1
    return offsets[found], offsets[last] + 1, found + len(needle)
