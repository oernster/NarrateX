"""Reading a title and an author out of the strings a library actually holds.

Every rule here was read off the reference library on 2026-09-19 rather than
imagined. The shapes that forced each one are named beside it, because a
normalisation rule with no example behind it is a guess that later looks like a
decision.

Nothing here touches the filesystem, the clock or a framework.
"""

from __future__ import annotations

import re
import unicodedata

# "Bachman Books, The" and "Ambler Warning, The" are sort forms typed into the
# title itself. The reader wants the article back at the front.
_TRAILING_ARTICLE = re.compile(r",\s*(the|a|an)\s*$", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

# A filename cannot carry a colon, so a colon in a title arrives as an
# underscore: "2001_ A Space Odyssey" and "2010_ Odyssey Two".
_UNDERSCORE_COLON = re.compile(r"_\s+")

# Calibre and the download tools both write "Surname, Forename"; a filename
# spells the same comma as an underscore, as in "Gaiman_ Neil". The same
# punctuation ALSO separates co-authors, as in "Larry Niven_ Edward M. Lerner".
# Measured on 2026-09-19: 28 files carry the sort form and 16 carry co-authors,
# and what tells them apart is the word count before the separator. A surname
# is one word; a complete name is two or more.
_SORT_NAME = re.compile(r"^([^,_]+)[,_]\s+(.+)$")

# "Cussler, Clive - Dirk Pitt 17 - Atlantis Found" puts the author first, in
# sort form, with the title (and sometimes a series) after it. 296 files do
# this. "Ambler Warning, The - Ludlum, Robert" looks identical to a machine
# until the article is noticed, which is why the article test is part of the
# rule rather than a refinement of it.
_ARTICLE_ONLY = re.compile(r"^(?:the|a|an)\b", re.IGNORECASE)

# "New Scientist - 19 April 2014" states an issue date where an author would
# go. 18 files do this; no author's name holds a month beside a number.
_MONTH = (
    "january|february|march|april|may|june|july|august|september|october"
    "|november|december"
)
_LOOKS_LIKE_A_DATE = re.compile(rf"\b(?:{_MONTH})\b", re.IGNORECASE)
_HOLDS_A_NUMBER = re.compile(r"\d")

# "American Gods - Neil Gaiman (2)" is a second copy of one book.
_COPY_MARKER = re.compile(r"\s*\((\d+)\)\s*$")

_TITLE_AUTHOR = " - "
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

UNKNOWN_AUTHOR = "Unknown author"


def _folded(value: str) -> str:
    """Accents removed, case flattened, punctuation dropped, spaces collapsed."""

    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    without_punctuation = _PUNCTUATION.sub(" ", stripped.lower())
    return _WHITESPACE.sub(" ", without_punctuation).strip()


def fold_for_search(value: str) -> str:
    """The form a search compares against: no accents, no case, no punctuation.

    Searching for "clarke" must find "Arthur C. Clarke" and searching for
    "emile" must find "Émile Zola", so the text typed and the text stored are
    folded the same way before either is looked at.
    """

    return _folded(value)


def display_title(raw: str) -> str:
    """The title as a reader would write it.

    "Bachman Books, The" becomes "The Bachman Books"; "2001_ A Space Odyssey"
    becomes "2001: A Space Odyssey".
    """

    value = _UNDERSCORE_COLON.sub(": ", raw.strip())
    match = _TRAILING_ARTICLE.search(value)
    if match:
        value = f"{match.group(1).title()} {value[: match.start()].strip()}"
    return _WHITESPACE.sub(" ", value).strip()


def display_author(raw: str) -> str:
    """The author as a reader would write it.

    "Child, Lee" and "Gaiman_ Neil" both become forename first. A name holding
    no separator is already the way round the reader wants it.
    """

    value = _COPY_MARKER.sub("", raw.strip())
    match = _SORT_NAME.match(value)
    if match:
        before, after = match.group(1).strip(), match.group(2).strip()
        if len(before.split()) == 1:
            value = f"{after} {before}"
        else:
            value = f"{before}, {after}"
    return _WHITESPACE.sub(" ", value).strip()


def title_key(raw: str) -> str:
    """The comparison form of a title, with any article dropped entirely.

    An article is dropped rather than moved, so "The Stand", "Stand, The" and
    "Stand" all answer the same key.
    """

    return _LEADING_ARTICLE.sub("", _folded(display_title(raw))).strip()


def author_key(raw: str) -> str:
    """The comparison form of an author name, insensitive to the order written.

    "Arthur C Clarke", "Arthur C. Clarke" and "Clarke, Arthur C." all answer
    the same key, because the words are sorted before joining.
    """

    words = _folded(display_author(raw)).split()
    return " ".join(sorted(words))


def name_core(raw: str) -> str:
    """A name compared without its initials.

    "Iain Banks" and "Iain M. Banks" are one author written two ways; the
    library uses both. Dropping single letters leaves the words that carry the
    name, so the two answer one key. Used where two names must be RECOGNISED as
    one person; `author_key` remains the stricter comparison.
    """

    words = [word for word in _folded(display_author(raw)).split() if len(word) > 1]
    return " ".join(sorted(set(words)))


def _is_author_first(segment: str) -> bool:
    """True when this segment is a name in sort form rather than a title."""

    match = _SORT_NAME.match(segment.strip())
    if match is None or "_" in segment:
        return False
    if _ARTICLE_ONLY.match(match.group(2).strip()):
        return False
    return len(match.group(1).split()) <= 2


def _is_a_date(segment: str) -> bool:
    """True when this segment states an issue date rather than an author."""

    return bool(_LOOKS_LIKE_A_DATE.search(segment)) and bool(
        _HOLDS_A_NUMBER.search(segment)
    )


def split_filename(stem: str) -> tuple[str, str]:
    """A file stem read as `<title> - <author>`.

    Splitting on the LAST separator, because a title may hold one of its own:
    "Foundation and Empire - Isaac Asimov" splits once, while a title such as
    "Blood Meridian - Or the Evening Redness - Cormac McCarthy" must not split
    on the first.

    A stem holding no separator is a title with no author (FR-BS-022).
    """

    cleaned = _COPY_MARKER.sub("", stem.strip()).rstrip("- ").strip()
    if _TITLE_AUTHOR not in cleaned:
        return display_title(cleaned), UNKNOWN_AUTHOR
    # The remainder cannot be empty: `cleaned` never ends with the separator,
    # so nothing needs to guard against it.
    leading, _, remainder = cleaned.partition(_TITLE_AUTHOR)
    if _is_author_first(leading):
        return display_title(remainder), display_author(leading)
    title_part, _, author_part = cleaned.rpartition(_TITLE_AUTHOR)
    if _is_a_date(author_part):
        # The whole stem is the title: dropping the date would fold every issue
        # of a magazine into one work and lose all but one of them.
        return display_title(cleaned), UNKNOWN_AUTHOR
    # The title part cannot be empty here: the stem was stripped, so the
    # separator can never sit at its start. No guard for it, because a guard
    # against the impossible teaches the next reader that it is possible.
    return display_title(title_part), display_author(author_part) or UNKNOWN_AUTHOR


def copy_number(stem: str) -> int:
    """The `(2)` a duplicate download carries; 1 when the stem states none."""

    match = _COPY_MARKER.search(stem.strip())
    if match is None:
        return 1
    return int(match.group(1))


def sort_key(title: str, author: str) -> tuple[str, str]:
    """Author then title, which is the shelf's default ordering (FR-BS-053).

    An unknown author sorts last rather than under U, since a shelf opening on
    a block of unknowns says nothing about the library.
    """

    author_part = author_key(author)
    if not author_part or author == UNKNOWN_AUTHOR:
        return ("\uffff", title_key(title))
    return (author_part, title_key(title))
