"""Find the subscripts and superscripts a formula's plain notation marks.

The extracted text writes a script as "_{...}" or "^{...}" so the narrator can
say "O sub 2" and every offset stays a plain character index. The reading pane
typesets those marks instead of printing them: the markers are hidden and the
content is set small, below or above the line, nested as deep as the page
nested it. This module only finds them; how they look is the pane's business.

A marker counts only directly after a character and only when its group
closes: "x_{2}" is a script, "a _{ b" and an unclosed "_{" are left as text.

Pure: works on the text alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

_SUBSCRIPT_MARK = "_"
_SUPERSCRIPT_MARK = "^"
_OPEN = "{"
_CLOSE = "}"
_MARKER_WIDTH = len(_SUBSCRIPT_MARK + _OPEN)


class ScriptKind(Enum):
    MARKER = "marker"
    SUBSCRIPT = "subscript"
    SUPERSCRIPT = "superscript"


@dataclass(frozen=True, slots=True)
class ScriptRun:
    """A stretch of text and what it is: a marker else script content.

    `shifts` lists the nesting from the outside in, so "ω^{d_{k}}" gives the
    "k" (SUPERSCRIPT, SUBSCRIPT): raised once, then lowered from there.
    """

    start: int
    end: int
    kind: ScriptKind
    shifts: tuple[ScriptKind, ...] = ()


def _closing(text: str, opening: int) -> int | None:
    """Index of the brace closing the group opened at `opening`."""

    depth = 0
    for index in range(opening, len(text)):
        if text[index] == _OPEN:
            depth += 1
        elif text[index] == _CLOSE:
            depth -= 1
            if depth == 0:
                return index
    return None


def _runs(
    text: str, start: int, end: int, shifts: tuple[ScriptKind, ...]
) -> list[ScriptRun]:
    runs: list[ScriptRun] = []
    index = start
    while index < end:
        mark = text[index]
        opens = index + 1 < end and text[index + 1] == _OPEN
        follows = index > start and not text[index - 1].isspace()
        if mark not in (_SUBSCRIPT_MARK, _SUPERSCRIPT_MARK) or not (opens and follows):
            index += 1
            continue
        closing = _closing(text, index + 1)
        if closing is None or closing >= end:
            index += 1
            continue
        kind = (
            ScriptKind.SUBSCRIPT if mark == _SUBSCRIPT_MARK else ScriptKind.SUPERSCRIPT
        )
        inner = shifts + (kind,)
        content_start = index + _MARKER_WIDTH
        runs.append(ScriptRun(index, content_start, ScriptKind.MARKER))
        runs.append(ScriptRun(content_start, closing, kind, inner))
        runs.extend(_runs(text, content_start, closing, inner))
        runs.append(ScriptRun(closing, closing + 1, ScriptKind.MARKER))
        index = closing + 1
    return runs


def script_runs(
    text: str, start: int = 0, end: int | None = None
) -> tuple[ScriptRun, ...]:
    """Every marker and script content between `start` and `end`.

    Content runs nest: an outer script's run covers its inner one, which is
    listed after it, so applying them in order leaves each character with its
    innermost description.
    """

    stop = len(text) if end is None else end
    return tuple(_runs(text, start, stop, ()))
