"""Where an implicit product is written with the dot operator.

Both readers of a book's mathematics write "e^{i⋅π}" for what the page sets
as e raised to iπ: the EPUB from its MathML tree, the PDF from the characters
of a maths-font span. They share this vocabulary; the PDF also uses the
character test. Measured over the formulas of one book in both formats, the
same five places take no dot: an upright word, a chemical formula ("CO_{2}",
"2CO"), a differential ("dt", "dI_{n}"), after a prefix operator ("ΔD_{n}",
"∂f") and among the indices of a subscript ("J_{ij}").

Pure: works on text alone.
"""

from __future__ import annotations

# The dot operator, written between the factors of an implicit product.
PRODUCT_DOT = "⋅"

# Signs that act on what follows them, so no product dot is written after.
PREFIX_OPERATORS = frozenset({"Δ", "∂", "∇"})

# The letter that opens a differential, as in "dt".
DIFFERENTIAL = "d"


def _is_capital(char: str) -> bool:
    return char.isascii() and char.isupper()


def joins_as_product(before: str, left: str, right: str) -> bool:
    """Whether `left` then `right`, set hard together, are two factors.

    `before` is the character ahead of `left`; empty at the start. Read
    for a maths-font span, where every letter is a variable of its own: a
    Word-built PDF sets function names and words in the text face.
    """

    if not right.isalpha() or not left.isalnum():
        return False
    if left in PREFIX_OPERATORS:
        return False
    if left == DIFFERENTIAL and not before.isalnum():
        return False
    if _is_capital(right) and (_is_capital(left) or left.isdigit()):
        return False
    return True


def mark_products(text: str) -> str:
    """The text with the dot written between each pair of factors."""

    out: list[str] = []
    for index, char in enumerate(text):
        if index and joins_as_product(
            text[index - 2] if index > 1 else "", text[index - 1], char
        ):
            out.append(PRODUCT_DOT)
        out.append(char)
    return "".join(out)


def is_chemical_join(left: str, right: str) -> bool:
    """Two element symbols set together, as the H and O of H_{2}O."""

    return _is_capital(left) and _is_capital(right)
