"""Detect extraction artefacts from text alone.

These predicates answer "does this line look like page furniture rather than
prose". They use no layout information, so plain text can use them as-is and
PDF can combine them with position and font evidence for a stronger verdict.

Each predicate is deliberately conservative. Mistaking prose for furniture
deletes something the reader wanted; mistaking furniture for prose merely
leaves a blemish, which the narrator's own sanitisation already softens.
"""

from __future__ import annotations

import re

from voice_reader.domain.text_patterns import contains_dotted_leader, normalize_dotlikes

# A folio is at most four digits. Longer runs are data, not page numbers.
_MAX_FOLIO_DIGITS = 4

_ARABIC_FOLIO = re.compile(rf"^\W*\d{{1,{_MAX_FOLIO_DIGITS}}}\W*$")
_ROMAN_FOLIO = re.compile(r"^\W*[ivxlcdm]+\W*$", re.IGNORECASE)
_LABELLED_FOLIO = re.compile(r"^\W*page\s+\d+\W*$", re.IGNORECASE)

# A contents line ends with the page it points at, in arabic or roman. The
# leader may run straight into the number ("Title...7") or be spaced away from
# it ("Title . . . 7"), so the boundary only rules out a number welded to a
# word ("Chapter7").
_TRAILING_FOLIO = re.compile(
    r"(?<![A-Za-z])(\d{1,4}|[ivxlcdm]+)\s*$",
    re.IGNORECASE,
)

# Four or more dots, spaced or not. Prose ellipses are three, so this is the
# line between a leader and ordinary punctuation.
_MIN_LEADER_DOTS = 4
_LONG_LEADER = re.compile(rf"(?:\.\s*){{{_MIN_LEADER_DOTS},}}")


def is_folio(text: str) -> bool:
    """Whether the line is nothing but a page number.

    Covers arabic (`12`), roman (`xiv`) and labelled (`Page 12`) forms, each
    tolerating surrounding punctuation such as `- 12 -`.
    """

    line = str(text or "").strip()
    if not line:
        return False
    if _LABELLED_FOLIO.match(line):
        return True
    if _ARABIC_FOLIO.match(line):
        return True
    return bool(_ROMAN_FOLIO.match(line))


def is_contents_entry(text: str) -> bool:
    """Whether the line is a table-of-contents entry with a dotted leader.

    Two shapes count, because real extraction produces both:

    - a leader and its page number on one line, `Prologue ..... 23`
    - a leader alone, `Prologue . . . . . . .`, because a two-column contents
      page often extracts the titles and the page numbers as separate lines

    The second shape is why a trailing number cannot be required. What
    separates it from prose is leader *length*: an ellipsis is three dots, a
    leader is a run of them. Requiring a long run keeps "He paused... then
    left" out without needing a page number to confirm it.
    """

    line = normalize_dotlikes(str(text or "")).strip()
    if not line:
        return False
    if _LONG_LEADER.search(line):
        return True
    if not contains_dotted_leader(line):
        return False
    return bool(_TRAILING_FOLIO.search(line))


def is_artefact(text: str) -> bool:
    """Whether the line is page furniture on textual evidence alone."""

    return is_folio(text) or is_contents_entry(text)
