"""Write MathML presentation markup in the plain notation the PDF path uses.

An EPUB built by pandoc states each formula twice inside one `<math>` element:
the presentation tree a reader sees plus the LaTeX it came from as an
annotation. Flattened to text, both come out: every token spaced apart, then
the source, so "e^{iθ}" read "e i θ ... e^{i\\theta}". This reads only the
presentation tree and writes the notation `pdf_mathematics` writes ("e^{i⋅θ}",
"∑_{k = 0}^{m}"), so the two formats of one book read alike and the narrator
speaks both the same way.

An implicit product is written with the dot operator, as the author reads it:
"e^{i⋅π}". Measured over the 175 formulas of a pandoc-built book, a dot
between every two neighbouring operands would be wrong in five places, each
exempted here: an upright word set letter by letter ("available", "kg/mol");
a chemical formula ("CO_{2}", "2CO"); a differential ("dt", "dI_{n}"); a
prefix operator ("ΔD_{n}", "∂f"); and the indices of a subscript ("J_{ij}").

Pure: the caller hands over a tree of `MathNode`, built from whatever parser
it uses.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum

from voice_reader.domain.document.mathml_rules import (
    COMBINING_ACCENTS,
    DIFFERENTIAL,
    FUNCTION_APPLICATION,
    INVISIBLE_TIMES,
    OPENING_FENCES,
    OPERATOR_SPELLINGS,
    PREFIX_OPERATORS,
    PRODUCT_DOT,
    ROWS,
    SIGNS,
    SILENT,
    THOUSANDS_GROUP,
)
from voice_reader.domain.document.maths_notation_text import (
    BIG_OPERATORS,
    fold_text,
    fraction_text,
    is_relation,
    tidy_spacing,
)

__all__ = ["PRODUCT_DOT", "MathNode", "render_mathml"]


@dataclass(frozen=True, slots=True)
class MathNode:
    """One element of a MathML presentation tree."""

    tag: str
    text: str = ""
    upright: bool = False
    children: tuple[MathNode, ...] = ()


class _Kind(Enum):
    OPERAND = "operand"
    OPERATOR = "operator"
    PREFIX = "prefix"
    FUNCTION = "function"
    BIG_OPERATOR = "big operator"
    WORD = "word"
    SPACE = "space"


@dataclass(frozen=True, slots=True)
class _Piece:
    text: str
    kind: _Kind
    # The letter or number an operand is built on, when it is a single one:
    # the base of "D_{n}" is "D". Chemistry and differentials are told by it.
    base: str = ""
    # A subscript of digits alone, as chemistry writes one.
    numeric_subscript: bool = False


@dataclass(frozen=True, slots=True)
class _Context:
    # Inside a subscript, neighbouring letters are indices ("J_{ij}"), not a
    # product, so no dot is written between them.
    indices: bool = False


def _leaf(node: MathNode) -> _Piece:
    text = node.text.strip()
    if node.tag == "mspace" or not text:
        return _Piece(" ", _Kind.SPACE)
    if node.tag == "mtext":
        return _Piece(text, _Kind.WORD)
    if node.tag == "mn":
        return _Piece(text, _Kind.OPERAND, base=text)
    if text in BIG_OPERATORS:
        return _Piece(text, _Kind.BIG_OPERATOR)
    if text in PREFIX_OPERATORS:
        return _Piece(text, _Kind.PREFIX)
    if node.tag == "mi":
        # Pandoc writes "+", "/" and "." as identifiers; they are operators.
        folded = fold_text(text, maths=False)
        if not folded.isalnum():
            return _operator(folded)
        if len(folded) > 1:
            return _Piece(folded, _Kind.FUNCTION)
        if node.upright and folded.isascii():
            return _Piece(folded, _Kind.WORD)
        return _Piece(folded, _Kind.OPERAND, base=folded)
    return _operator(text)


def _operator(text: str) -> _Piece:
    # A negated arrow arrives as the arrow plus a combining stroke; composed,
    # it is the one sign a reader and the narrator both know.
    composed = unicodedata.normalize("NFC", OPERATOR_SPELLINGS.get(text, text))
    return _Piece(composed, _Kind.OPERATOR)


def _is_chemical(piece: _Piece) -> bool:
    """An element symbol: one capital, alone or with a count of atoms."""

    return (
        piece.kind is _Kind.OPERAND
        and len(piece.base) == 1
        and piece.base.isascii()
        and piece.base.isupper()
        and (piece.text == piece.base or piece.numeric_subscript)
    )


def _is_differential(piece: _Piece, before: _Piece | None) -> bool:
    """A bare "d" opening a term, as in "f(s) ds" or "dI_{n}/dt"."""

    return (
        piece.kind is _Kind.OPERAND
        and piece.text == DIFFERENTIAL
        and (before is None or before.kind is not _Kind.OPERAND)
    )


def _takes_product(
    before: _Piece | None, left: _Piece, right: _Piece, context: _Context
) -> bool:
    if context.indices:
        return False
    if left.kind is not _Kind.OPERAND or right.kind is not _Kind.OPERAND:
        return False
    if _is_differential(left, before):
        return False
    if _is_chemical(right) and (_is_chemical(left) or left.base.isdigit()):
        return False
    return right.text[:1].isalnum() or right.text[:1] == "("


def _is_thousands(previous: _Piece | None, following: _Piece | None) -> bool:
    """The comma of "177,147": digits either side, three of them after."""

    return (
        previous is not None
        and following is not None
        and previous.text.isdigit()
        and following.text.isdigit()
        and len(following.text) == THOUSANDS_GROUP
    )


def _operator_text(
    piece: _Piece, previous: _Piece | None, following: _Piece | None
) -> str:
    text = piece.text
    if text == FUNCTION_APPLICATION:
        return " "
    if text == INVISIBLE_TIMES:
        return PRODUCT_DOT
    if is_relation(text):
        return f" {text} "
    if text == "," and _is_thousands(previous, following):
        return text
    if text in (",", ";"):
        return f"{text} "
    lead = " " if previous is not None and previous.kind is _Kind.BIG_OPERATOR else ""
    binary = previous is not None and (
        previous.kind in (_Kind.OPERAND, _Kind.WORD)
        or previous.text.endswith((")", "]", "}"))
    )
    if text in SIGNS and binary:
        return f" {text} "
    return lead + text


def _merge_words(pieces: list[_Piece]) -> list[_Piece]:
    """Upright letters set one by one are the word they spell."""

    merged: list[_Piece] = []
    for piece in pieces:
        if piece.kind is _Kind.WORD and merged and merged[-1].kind is _Kind.WORD:
            merged[-1] = _Piece(merged[-1].text + piece.text, _Kind.WORD)
        else:
            merged.append(piece)
    return merged


def _separator(
    before: _Piece | None, previous: _Piece, piece: _Piece, context: _Context
) -> str:
    if _takes_product(before, previous, piece, context):
        return PRODUCT_DOT
    if previous.kind is _Kind.OPERATOR and previous.text in OPENING_FENCES:
        return ""
    spaced = (_Kind.FUNCTION, _Kind.BIG_OPERATOR)
    if piece.kind in spaced or previous.kind in spaced:
        return " "
    # "1/2 O_{2}" but "2CO_{2}" and "ΛCDM": only a compound operand stands
    # apart from the word after it.
    if piece.kind is _Kind.WORD and previous.kind is _Kind.OPERAND:
        return "" if previous.base else " "
    return ""


def _join(pieces: list[_Piece], context: _Context) -> str:
    out = ""
    for index, piece in enumerate(pieces):
        previous = pieces[index - 1] if index else None
        before = pieces[index - 2] if index > 1 else None
        following = pieces[index + 1] if index + 1 < len(pieces) else None
        if piece.kind is _Kind.OPERATOR:
            out += _operator_text(piece, previous, following)
            continue
        if previous is not None:
            out += _separator(before, previous, piece, context)
        out += piece.text
    return out


def _row(children: tuple[MathNode, ...], context: _Context) -> _Piece:
    pieces = _merge_words([_piece(child, context) for child in children])
    pieces = [p for p in pieces if p.text]
    if len(pieces) == 1:
        return pieces[0]
    text = _join(pieces, context)
    # "cos" followed by the function application sign is a function name.
    if pieces and pieces[-1].text == FUNCTION_APPLICATION:
        return _Piece(text.strip(), _Kind.FUNCTION)
    return _Piece(text, _Kind.OPERAND)


def _scripted(node: MathNode, context: _Context) -> _Piece:
    base = _piece(node.children[0], context)
    lowered = _Context(indices=True)
    scripts = [
        tidy_spacing(
            _piece(child, lowered if index == 0 else context).text
            if node.tag in ("msub", "munder", "msubsup", "munderover")
            else _piece(child, context).text
        )
        for index, child in enumerate(node.children[1:])
    ]
    if node.tag == "mover" and base.kind is not _Kind.BIG_OPERATOR and scripts:
        mark = COMBINING_ACCENTS.get(scripts[0])
        if mark is not None:
            return _Piece(base.text + mark, base.kind, base=base.base)
    lower = upper = None
    if node.tag in ("msub", "munder"):
        lower = scripts[0]
    elif node.tag in ("msup", "mover"):
        upper = scripts[0]
    else:
        lower, upper = scripts[0], scripts[1]
    text = base.text.strip()
    if lower is not None:
        text += f"_{{{lower}}}"
    if upper is not None:
        text += f"^{{{upper}}}"
    kept = (_Kind.BIG_OPERATOR, _Kind.FUNCTION, _Kind.WORD)
    return _Piece(
        text,
        base.kind if base.kind in kept else _Kind.OPERAND,
        base=base.base if base.kind is _Kind.OPERAND else "",
        numeric_subscript=lower is not None and lower.isdigit(),
    )


def _table(node: MathNode, context: _Context) -> _Piece:
    rows = []
    for row in node.children:
        cells = [tidy_spacing(_piece(cell, context).text) for cell in row.children]
        rows.append(", ".join(cell for cell in cells if cell))
    return _Piece("; ".join(rows), _Kind.OPERAND)


def _radical(node: MathNode, context: _Context) -> _Piece:
    parts = [tidy_spacing(_piece(child, context).text) for child in node.children]
    if node.tag == "mroot":
        return _Piece(f"√^{{{parts[1]}}}({parts[0]})", _Kind.OPERAND)
    return _Piece(f"√({' '.join(parts)})", _Kind.OPERAND)


def _piece(node: MathNode, context: _Context) -> _Piece:
    if node.tag in SILENT:
        return _Piece("", _Kind.SPACE)
    if node.tag == "semantics":
        if not node.children:
            return _Piece("", _Kind.SPACE)
        return _piece(node.children[0], context)
    if node.tag in ROWS:
        return _row(node.children, context)
    if node.tag == "mfrac":
        halves = [tidy_spacing(_piece(c, context).text) for c in node.children]
        return _Piece(fraction_text(halves[0], halves[1]), _Kind.OPERAND)
    if node.tag in ("msqrt", "mroot"):
        return _radical(node, context)
    if node.tag in ("msub", "msup", "msubsup", "munder", "mover", "munderover"):
        return _scripted(node, context)
    if node.tag == "mtable":
        return _table(node, context)
    if node.children:
        return _row(node.children, context)
    return _leaf(node)


def render_mathml(node: MathNode) -> str:
    """One formula as a line of text in the plain notation."""

    return tidy_spacing(_piece(node, _Context()).text)
