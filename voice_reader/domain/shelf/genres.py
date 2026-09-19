"""Turning the subjects a file states into genres a reader can filter by.

FR-BS-040, FR-BS-041, FR-BS-043, FR-BS-048 and FR-BS-049. The catalogue and the
alias table live next door in `genre_catalogue`; this module is the rule that
uses them.

Three things happen to a raw subject, in this order; each one exists
because the reference library forced it:

1. **Entity references are decoded.** `Mystery &amp; Detective` appears 70
   times. Splitting it undecoded yields the genre `Mystery &amp`, which matches
   nothing and reads as a defect on screen.
2. **It is split.** One subject string routinely states several genres, joined
   by a semicolon, a comma, a solidus or an ampersand.
3. **Each piece is folded and looked up.** A piece reaching nothing is reported
   rather than discarded, since that report is how the alias table grows.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from voice_reader.domain.shelf.genre_catalogue import (
    ALIASES,
    MAINS,
    NAMES,
    NOT_A_GENRE,
    SAYS_NOTHING,
    STYLE_PARENT,
)

# The separators the sources actually use. Measured, not assumed.
_SEPARATORS = re.compile(r"[;,/&]")
_FOLD = re.compile(r"[^a-z0-9]+")


def fold(value: str) -> str:
    """Case, punctuation and spacing removed, so one spelling is one key."""

    return _FOLD.sub("", html.unescape(value).lower())


def _build_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for name in NAMES:
        index[fold(name)] = name
    for name, forms in ALIASES.items():
        for form in forms:
            index[form] = name
    return index


_INDEX: dict[str, str] = _build_index()


@dataclass(frozen=True, slots=True)
class GenreReading:
    """What one book's subjects came to.

    `genres` holds every name reached, styles and their mains together, so a
    filter never has to walk the catalogue to answer a tick (FR-BS-043).
    `unmatched` holds the pieces that reached nothing, in the spelling the file
    used, for the report FR-BS-041 requires.
    """

    genres: tuple[str, ...]
    unmatched: tuple[str, ...]

    @property
    def mains(self) -> tuple[str, ...]:
        return tuple(name for name in self.genres if name in MAINS)

    def carries(self, name: str) -> bool:
        return name in self.genres


def pieces_of(subject: str) -> tuple[str, ...]:
    """One raw subject string broken into the names it states."""

    decoded = html.unescape(subject)
    return tuple(piece.strip() for piece in _SEPARATORS.split(decoded) if piece.strip())


def name_for(piece: str) -> str | None:
    """The catalogue name this piece reaches; None when it reaches nothing.

    A piece that says nothing about the book or that names a provenance rather
    than a genre also answers None; `is_ignorable` tells the two apart.
    """

    key = fold(piece)
    if not key or key in SAYS_NOTHING or key in NOT_A_GENRE:
        return None
    return _INDEX.get(key)


def is_ignorable(piece: str) -> bool:
    """True when a piece is deliberately dropped rather than reported."""

    key = fold(piece)
    return not key or key in SAYS_NOTHING or key in NOT_A_GENRE


def with_mains(names: frozenset[str]) -> frozenset[str]:
    """Every name given, plus the main above any style among them."""

    parents = {STYLE_PARENT[name] for name in names if name in STYLE_PARENT}
    return names | parents


def read(subjects: tuple[str, ...]) -> GenreReading:
    """Every genre a book's subjects reach, with whatever reached nothing.

    Ordering is the catalogue's own rather than the file's, so two books
    carrying the same genres always read the same way round.
    """

    found: set[str] = set()
    unmatched: list[str] = []
    for subject in subjects:
        for piece in pieces_of(subject):
            if is_ignorable(piece):
                continue
            name = _INDEX.get(fold(piece))
            if name is None:
                unmatched.append(piece)
                continue
            found.add(name)
    complete = with_mains(frozenset(found))
    ordered = tuple(name for name in _catalogue_order() if name in complete)
    return GenreReading(genres=ordered, unmatched=tuple(dict.fromkeys(unmatched)))


def _catalogue_order() -> tuple[str, ...]:
    order: list[str] = []
    for main in MAINS:
        order.append(main)
        order.extend(style for style, parent in STYLE_PARENT.items() if parent == main)
    return tuple(order)
