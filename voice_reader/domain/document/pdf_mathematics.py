"""Read back the mathematics a PDF set in a maths font.

A PDF typeset from Word or LaTeX sets its mathematics in a dedicated font;
three things go wrong when those glyphs come back as plain text. All three were
measured on a Word-produced book set in Cambria Math.

- Variables arrive as Mathematical Alphanumeric Symbols (U+1D400 to U+1D7FF):
  the italic "M" of a formula is not the letter M. The reading pane's face has
  no glyph for it and the narrator's phonemiser knows none of them, so a
  formula shows as boxes and is spoken as nothing.
- The large operators and fences have no Unicode mapping in the file at all,
  so a summation sign comes back as a Sinhala letter.
- Nothing says which pieces are subscripts, superscripts or limits. They are
  told apart on the page by size and by a shift off the baseline, which the
  text dump throws away: "M" with "n" below and "min" above reads "Mn min".

This module is the span level: the pieces of one visual row become one line
of text in a plain notation, "M_{n}^{min}", with a script marked by braces so a
narrator can say it and a reader can see where it starts and ends. The rows
above that, fractions, limits and an equation the extractor split across
blocks, belong to `pdf_mathematics_layout`. The characters below it, the
folded letters, the unmapped glyphs and the relation padding, belong to
`maths_notation_text`, which the EPUB's reader shares.

Pure: every rule here is testable without opening a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from voice_reader.domain.document.maths_notation_text import (
    REPEATED_SPACES,
    fold_text,
    fraction_text,
)
from voice_reader.domain.document.product_marks import (
    PRODUCT_DOT,
    is_chemical_join,
    mark_products,
)

# A font whose name carries one of these sets mathematics. "math" is Cambria
# Math, the measured case; it also names STIX Math, Latin Modern Math and XITS
# Math. The other three are the names of Computer Modern's maths fonts, which
# a LaTeX-produced PDF embeds; they are matched on their published names and
# have not been measured here.
_MATHS_FONT_MARKERS = ("math", "cmmi", "cmsy", "cmex")

# The name a composite piece (a fraction, an operator with its limits) carries,
# so it reads as mathematics for the spacing rule at a junction.
COMPOSITE_FONT = "mathematics"

# A piece set below this fraction of its row's size is a sub or superscript.
SCRIPT_SIZE_RATIO = 0.9

# A smaller piece whose baseline sits further than this fraction of the row's
# size from the row's baseline is above or below it; nearer than that, it is
# merely small text on the row, such as a reduced "min".
_SCRIPT_SHIFT_RATIO = 0.1

# Two neighbouring pieces further apart than this fraction of the smaller
# size have a word space between them that the extraction did not report.
_WORD_GAP_RATIO = 0.2


@dataclass(frozen=True, slots=True)
class PdfSpan:
    """One run of text in one font at one size, with its box on the page."""

    text: str
    font: str
    size: float
    bold: bool
    left: float
    top: float
    right: float
    bottom: float
    baseline: float

    @property
    def in_maths_font(self) -> bool:
        name = self.font.casefold()
        return any(marker in name for marker in _MATHS_FONT_MARKERS)

    @property
    def centre(self) -> float:
        return (self.left + self.right) / 2


class _Shift(Enum):
    SUBSCRIPT = "sub"
    SUPERSCRIPT = "super"
    INLINE = "inline"


def piece_from_span(span: PdfSpan) -> PdfSpan | None:
    """The span with its text folded, else None when it has no text at all."""

    if not span.text:
        return None
    return replace(span, text=fold_text(span.text, maths=span.in_maths_font))


def is_script(piece: PdfSpan, *, size: float) -> bool:
    """Whether a piece is a sub or superscript of a row set at `size`."""

    return not piece.text.isspace() and piece.size < SCRIPT_SIZE_RATIO * size


def _needs_space(previous: PdfSpan, piece: PdfSpan) -> bool:
    if previous.text[-1].isspace() or piece.text[0].isspace():
        return False
    gap = piece.left - previous.right
    if gap > _WORD_GAP_RATIO * min(previous.size, piece.size):
        return True
    # An italic variable set hard against a roman word is two words: the
    # extraction reports "Dindependent" where the page shows "D independent".
    return (
        previous.in_maths_font != piece.in_maths_font
        and previous.text[-1].isalnum()
        and piece.text[0].isalnum()
    )


def _append(out: str, previous: PdfSpan | None, piece: PdfSpan) -> str:
    if previous is not None and _needs_space(previous, piece):
        out += " "
    return out + piece.text


def _shift_of(piece: PdfSpan, *, baseline: float, size: float) -> _Shift:
    shift = piece.baseline - baseline
    if shift > _SCRIPT_SHIFT_RATIO * size:
        return _Shift.SUBSCRIPT
    if shift < -_SCRIPT_SHIFT_RATIO * size:
        return _Shift.SUPERSCRIPT
    return _Shift.INLINE


def _shift_groups(
    run: list[PdfSpan], *, baseline: float, size: float
) -> list[tuple[_Shift, list[PdfSpan]]]:
    groups: list[tuple[_Shift, list[PdfSpan]]] = []
    for piece in run:
        shift = _shift_of(piece, baseline=baseline, size=size)
        if groups and groups[-1][0] is shift:
            groups[-1][1].append(piece)
        else:
            groups.append((shift, [piece]))
    return groups


def _overlap(first: list[PdfSpan], second: list[PdfSpan]) -> bool:
    return min(p.right for p in first) > max(p.left for p in second) and min(
        p.right for p in second
    ) > max(p.left for p in first)


def abuts(previous: PdfSpan, piece: PdfSpan) -> bool:
    """Whether `piece` starts where `previous` ends, as a script does its base."""

    return piece.left - previous.right <= _WORD_GAP_RATIO * piece.size


def _stacked_pair(
    groups: list[tuple[_Shift, list[PdfSpan]]],
) -> tuple[list[PdfSpan], list[PdfSpan]] | None:
    """The (upper, lower) halves of a run that is one script over another."""

    if len(groups) != 2:
        return None
    by_shift = {shift: pieces for shift, pieces in groups}
    if set(by_shift) != {_Shift.SUPERSCRIPT, _Shift.SUBSCRIPT}:
        return None
    if not _overlap(groups[0][1], groups[1][1]):
        return None
    return by_shift[_Shift.SUPERSCRIPT], by_shift[_Shift.SUBSCRIPT]


def _flush_scripts(
    out: str,
    previous: PdfSpan | None,
    run: list[PdfSpan],
    *,
    baseline: float,
    size: float,
    products: bool,
) -> tuple[str, PdfSpan | None]:
    if not run:
        return out, previous
    groups = _shift_groups(run, baseline=baseline, size=size)
    pair = _stacked_pair(groups)
    if pair is not None:
        upper, lower = pair
        if previous is None or not abuts(previous, run[0]):
            # A small numerator over a small denominator standing clear of
            # what precedes it, as the "1/2" in a reaction. Against a base
            # it is that base's superscript over its subscript instead.
            fraction = fraction_text(render_group(upper), render_group(lower))
            return f"{out} {fraction} ", run[-1]
        # Subscript before superscript, the order the narrator reads limits in.
        groups = [(_Shift.SUBSCRIPT, lower), (_Shift.SUPERSCRIPT, upper)]
    for shift, pieces in groups:
        inner = render_group(
            pieces, products=products and shift is not _Shift.SUBSCRIPT
        )
        if shift is _Shift.SUBSCRIPT:
            out += f"_{{{inner}}}"
        elif shift is _Shift.SUPERSCRIPT:
            out += f"^{{{inner}}}"
        else:
            out = _append(
                out,
                previous,
                replace(pieces[0], text=inner, right=max(p.right for p in pieces)),
            )
        previous = pieces[-1]
    return out, previous


def _sets_variables(piece: PdfSpan) -> bool:
    """A maths-font span read as it was set, not a rebuilt composite."""

    return piece.in_maths_font and piece.font != COMPOSITE_FONT


def _after_scripts(
    base: PdfSpan | None, run: list[PdfSpan], piece: PdfSpan, *, products: bool
) -> str:
    """What separates a closing script from the factor set after it.

    "d_{k}3^{k}" and "R_{g}T" are two factors and take the dot; "H_{2}O" is
    one molecule (a count of atoms between two element symbols) and takes
    nothing; anything else after a script stands a space apart.
    """

    counted = all(p.text.strip().isdigit() for p in run)
    if (
        counted
        and base is not None
        and is_chemical_join(base.text.rstrip()[-1:], piece.text[:1])
    ):
        return ""
    # Set clear of the script, as the columns of a vector are, it is a term
    # of its own; only a factor set hard against the script multiplies it.
    if not abuts(run[-1], piece):
        return " "
    if products and (_sets_variables(piece) or piece.font == COMPOSITE_FONT):
        return PRODUCT_DOT
    return " "


def _starts_factor(piece: PdfSpan) -> bool:
    """Whether a piece opens with something a product can multiply.

    A piece opening with a space was set apart and multiplies nothing. A
    rebuilt fraction is padded by the rebuild itself, so it is read past that.
    """

    if piece.font == COMPOSITE_FONT:
        return piece.text.lstrip()[:1] == "("
    return piece.text[:1].isalnum()


def render_level(
    pieces: list[PdfSpan], *, baseline: float, size: float, products: bool = True
) -> str:
    """One row of pieces as text, scripts marked relative to the row.

    Pieces are read left to right. A run of pieces smaller than the row is a
    script of what precedes it, below the baseline a subscript and above it a
    superscript; a script set smaller still inside that run is a script of the
    script, rendered by the same rule one level down. With `products`, an
    implicit product takes the dot; a subscript's indices are read without.
    """

    ordered = sorted(pieces, key=lambda p: (p.left, p.baseline))
    out = ""
    previous: PdfSpan | None = None
    base: PdfSpan | None = None
    run: list[PdfSpan] = []
    for piece in ordered:
        if is_script(piece, size=size):
            run.append(piece)
            continue
        out, previous = _flush_scripts(
            out, previous, run, baseline=baseline, size=size, products=products
        )
        if run and _starts_factor(piece):
            separator = _after_scripts(base, run, piece, products=products)
            out += separator
            if separator == PRODUCT_DOT:
                piece = replace(piece, text=piece.text.lstrip())
        run = []
        if products and _sets_variables(piece):
            piece = replace(piece, text=mark_products(piece.text))
        out = _append(out, previous, piece)
        previous = base = piece
    out, _ = _flush_scripts(
        out, previous, run, baseline=baseline, size=size, products=products
    )
    # A factor follows its dot hard: "C_{j}⋅((t", never "C_{j}⋅ ((t".
    out = out.replace(PRODUCT_DOT + " ", PRODUCT_DOT)
    return REPEATED_SPACES.sub(" ", out)


def render_group(pieces: list[PdfSpan], *, products: bool = True) -> str:
    """Render pieces as a row of their own, its size and baseline the largest's."""

    ordered = sorted(pieces, key=lambda p: p.left)
    size = max(p.size for p in ordered)
    baseline = next(p.baseline for p in ordered if p.size == size)
    return render_level(
        ordered, baseline=baseline, size=size, products=products
    ).strip()
