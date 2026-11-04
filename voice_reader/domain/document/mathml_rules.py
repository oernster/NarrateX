"""The fixed vocabulary `mathml_notation` reads MathML with.

Held apart from the rules that use it so each table has one home and the
renderer stays a reading of structure.
"""

from __future__ import annotations

# The dot operator, written between the factors of an implicit product.
PRODUCT_DOT = "⋅"

FUNCTION_APPLICATION = "⁡"
INVISIBLE_TIMES = "⁢"

# A thousands separator groups digits in threes.
THOUSANDS_GROUP = 3

# Elements whose children read in a row, as one expression.
ROWS = frozenset({"math", "mrow", "mstyle", "mpadded", "menclose", "mtd", "merror"})

# Elements that carry nothing a reader sees.
SILENT = frozenset({"annotation", "annotation-xml", "mphantom", "none"})

# Signs that act on what follows them, so no product dot is written after.
PREFIX_OPERATORS = frozenset({"Δ", "∂", "∇"})

# The letter that opens a differential, as in "dt".
DIFFERENTIAL = "d"

# Signs set with a space either side when they join two terms.
SIGNS = frozenset({"+", "−", "±", "×", "∖"})

# Brackets that open a group: what follows sits hard against them.
OPENING_FENCES = frozenset({"(", "[", "{", chr(0x2308), chr(0x230A)})

# How pandoc writes a few operators, against the character a reader expects.
OPERATOR_SPELLINGS = {"\\": "∖", "-": "−"}

# Accents set over a letter, as the combining mark that sets them on it.
COMBINING_ACCENTS = {
    "̇": "̇",
    "˙": "̇",
    "¨": "̈",
    "¯": "̄",
    "‾": "̄",
    "^": "̂",
    "ˆ": "̂",
    "~": "̃",
    "˜": "̃",
    "→": "⃗",
}
