"""The words a book divides itself with; how it numbers them.

One home for this vocabulary, because two rules ask about it: deciding where
the body of a book begins (`reading_start`) and recognising a chapter heading
in a book that marked none up (`text_headings`). The two ask different
questions of the same words, so the words live here and the questions stay
where they belong.
"""

from __future__ import annotations

import re

# Divisions that carry a number: "Chapter 12", "Part II", "Book Three".
NUMBERED_WORDS = frozenset({"chapter", "part", "book", "section", "volume", "appendix"})

# Divisions that open the body of a book and carry no number of their own.
FRONT_OPENINGS = frozenset(
    {
        "prologue",
        "introduction",
        "foreword",
        "preface",
        "acknowledgements",
        "acknowledgments",
    }
)

# Divisions that are neither numbered nor an opening. An epilogue is a heading
# and is not where a book starts, which is why it is kept apart from the set
# above rather than folded into it.
OTHER_DIVISIONS = frozenset({"epilogue", "interlude", "afterword", "coda"})

# How English writes the number after such a word. Digits, roman numerals, the
# number words and the ordinals, with an optional "the" in front of the last
# ("Part the First"). This is a fact about the language rather than a value
# anything is tuned to.
_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen"
    "|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty"
    "|fifty|sixty|seventy|eighty|ninety|hundred"
)
_ORDINAL_WORDS = (
    "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    "|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth"
    "|eighteenth|nineteenth|twentieth|last"
)
_NUMERAL = rf"(?:\d+|[ivxlcdm]+|(?:the\s+)?(?:{_NUMBER_WORDS}|{_ORDINAL_WORDS}))"

_NUMBERED_DIVISION = re.compile(
    rf"^(?:{'|'.join(sorted(NUMBERED_WORDS))})\b[\s.:\u2013-]*{_NUMERAL}\b",
    re.IGNORECASE,
)

# A leading division word with no number behind it, which is what an ordinary
# sentence looks like: "Book design by Virginia Norey" opens a real book and is
# not a heading. Measured on 2026-09-20, it was the one false heading a keyword
# rule produced across ten books.
_BARE_DIVISION_WORD = re.compile(
    rf"^(?:{'|'.join(sorted(NUMBERED_WORDS))})\b",
    re.IGNORECASE,
)


def is_numbered_division(text: str) -> bool:
    """Whether this reads as "Chapter 12", "Part II" or "Book the Third"."""

    return bool(_NUMBERED_DIVISION.match(str(text or "").strip()))


def opens_with_a_division_word(text: str) -> bool:
    """Whether this starts with a dividing word, numbered or not."""

    return bool(_BARE_DIVISION_WORD.match(str(text or "").strip()))


def is_named_division(text: str, *, words: frozenset[str]) -> bool:
    """Whether the whole of this text is one of `words`, bar a full stop."""

    return str(text or "").strip().rstrip(".").casefold() in words
