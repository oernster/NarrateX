"""The characters of written mathematics, whatever format they came from.

Both readers of a book's mathematics produce the same plain notation: the PDF
from the glyphs of a maths font, the EPUB from its MathML tree. The rules here
work on characters alone and are shared by both: folding a styled letter to
the plain one, reading the glyphs a maths font leaves unmapped, padding a
relation, tidying the spacing and writing a fraction on one line.

Pure: works on text alone.
"""

from __future__ import annotations

import re
import unicodedata

# Glyphs Cambria Math draws for the large operators and fences, which the PDF
# leaves without a Unicode mapping so they arrive as the code points of the
# glyph slots: Sinhala and Malayalam letters. Measured by reading each one in
# place: the summation sign sits under its limits, the integral sign before
# its integrand and the fences around a vector and a set difference.
_UNMAPPED_MATHS_GLYPHS = {
    "෍": "∑",  # n-ary summation
    "න": "∫",  # integral
    "ൣ": "(",
    "൧": ")",
    "൫": "(",
    "൯": ")",
}

# Operators that take limits above and below rather than beside them.
BIG_OPERATORS = frozenset({"∑", "∫", "∏"})

# Relations a maths font sets with no space on either side, because the
# spacing is drawn by position rather than by a space character. Padding them
# is what turns "N=" and "d_{k}∈{" into "N =" and "d_{k} ∈ {".
_RELATIONS = re.compile("([=<>≤≥≠≈≃∈∉⊂⊆∪∩" "→⟶↪⇒⇏⇔])")

# A plus or minus is binary (so padded) only when something it can operate on
# precedes it in the same run: "θ+" and "(t−s)" but not "{−1" or "^{−k}".
_BINARY_SIGN = re.compile(r"(?<=[\w)\]}])([+−])")

# A large operator set hard against its operand.
_BIG_OPERATOR_BEFORE = re.compile("([" + "".join(sorted(BIG_OPERATORS)) + r"])(?=\S)")

# A combining mark the file sets before the letter it belongs on, so the dot
# of a time derivative arrives as "̇M" and displays on the space before M.
_MARK_BEFORE_LETTER = re.compile(r"([̀-ͯ])(\w)")

_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?)\]])")

# The Mathematical Alphanumeric Symbols block: every character of it is a
# styled letter or digit whose compatibility decomposition is the plain one.
_MATHS_LETTERS = (0x1D400, 0x1D7FF)

# The Letterlike Symbols block holds the double-struck and script capitals of
# set notation among trademark and unit signs, so only a character whose plain
# form is one letter is folded: a trade mark sign is not "TM".
_LETTERLIKE = (0x2100, 0x214F)

REPEATED_SPACES = re.compile(" {2,}")


def _fold_letter(char: str) -> str:
    code = ord(char)
    if _MATHS_LETTERS[0] <= code <= _MATHS_LETTERS[1]:
        return unicodedata.normalize("NFKC", char)
    if _LETTERLIKE[0] <= code <= _LETTERLIKE[1]:
        folded = unicodedata.normalize("NFKC", char)
        if len(folded) == 1 and folded.isascii() and folded.isalpha():
            return folded
    return char


def fold_text(text: str, *, maths: bool) -> str:
    """Plain letters for styled ones; for a maths font, its glyphs and spacing.

    Letters are folded whatever the font, because a styled letter never
    appears in prose. The glyph table and the relation padding apply only to a
    maths font: a Sinhala book keeps its letters and a prose "=" stays as set.
    """

    chars = []
    for char in text:
        if maths and char in _UNMAPPED_MATHS_GLYPHS:
            chars.append(_UNMAPPED_MATHS_GLYPHS[char])
        else:
            chars.append(_fold_letter(char))
    folded = "".join(chars)
    if maths:
        folded = _MARK_BEFORE_LETTER.sub(r"\2\1", folded)
        folded = _RELATIONS.sub(r" \1 ", folded)
        folded = _BINARY_SIGN.sub(r" \1 ", folded)
        # "∫M" and "∫(R" read "∫ M" and "∫ (R", as the EPUB sets them.
        folded = _BIG_OPERATOR_BEFORE.sub(r"\1 ", folded)
    return folded


def is_relation(text: str) -> bool:
    """Whether `text` is one relation sign, set with a space either side."""

    return _RELATIONS.fullmatch(text) is not None


def tidy_spacing(text: str) -> str:
    """One space at most, none before a closing mark, none at either end."""

    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", REPEATED_SPACES.sub(" ", text)).strip()


# A numerator or denominator that can stand without fences: one token with no
# space and no arithmetic in it.
_ATOM = re.compile(r"[^\s()+=×−-]+")


def fraction_text(numerator: str, denominator: str) -> str:
    """ "1/((n−1)!)": each half fenced unless it is a single atom."""

    def fenced(text: str) -> str:
        return text if _ATOM.fullmatch(text) else f"({text})"

    return f"{fenced(numerator)}/{fenced(denominator)}"
