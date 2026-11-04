"""Say mathematics in words.

Measured on 2026-11-04 through Kokoro's own phonemiser: every symbol a formula
carries comes back as an unknown token, including a plain equals sign and the
Unicode minus, so a sentence that reads "M_{n} ≥ M_{min}" is spoken as "M N,
M min" with the relation silent. The Greek letters are unknown to it as well;
their names are not.

The notation this reads is the one the PDF extraction writes: a subscript as
"_{...}", a superscript as "^{...}" and a large operator's limits as the two
together, "∑_{k=0}^{m}", each group nesting as deep as the page did. Prose
never contains "_{", so nothing here fires on a book without mathematics
beyond the symbols themselves, each of which is said as the word it stands
for.
"""

from __future__ import annotations

import re

from voice_reader.domain.document.pdf_mathematics import tidy_spacing

_LIMITED_OPERATORS = {
    "∑": "the sum",
    "∫": "the integral",
    "∏": "the product",
}

_SUBSCRIPT = "_"
_SUPERSCRIPT = "^"
_OPEN = "{"
_CLOSE = "}"

_POWER_WORDS = {"2": "squared", "3": "cubed"}

_SYMBOL_WORDS = {
    "=": "equals",
    "+": "plus",
    "−": "minus",
    "×": "times",
    "⋅": "times",
    "±": "plus or minus",
    "≥": "greater than or equal to",
    "≤": "less than or equal to",
    "≠": "is not equal to",
    "≈": "is approximately",
    "≃": "is approximately",
    "∈": "in",
    "∉": "not in",
    "⊂": "is a subset of",
    "⊆": "is a subset of",
    "∪": "union",
    "∩": "intersection",
    "∖": "minus",
    "∞": "infinity",
    "∂": "partial",
    "∇": "nabla",
    "√": "the square root of",
    "→": "to",
    "⟶": "to",
    "↦": "maps to",
    "⇒": "implies",
    "⇏": "does not imply",
    "⇔": "if and only if",
    "∀": "for all",
    "∃": "there exists",
    chr(0x2308): "the ceiling of",
    chr(0x2309): "",
    chr(0x230A): "the floor of",
    chr(0x230B): "",
    "′": "prime",
    "″": "double prime",
    "∑": "the sum of",
    "∫": "the integral of",
    "∏": "the product of",
    # The dot of a time derivative, set after its letter by the extraction.
    "̇": "dot",
    # A faithful embedding. The same arrow marks a wrapped line in a PDF code
    # listing; the PDF assembly drops those marks before anything is said.
    "↪": "embeds into",
}

_GREEK_NAMES = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "ϵ": "epsilon",
    "ζ": "zeta",
    "η": "eta",
    "θ": "theta",
    "ϑ": "theta",
    "ι": "iota",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ν": "nu",
    "ξ": "xi",
    "ο": "omicron",
    "π": "pi",
    "ρ": "rho",
    "σ": "sigma",
    "ς": "sigma",
    "τ": "tau",
    "υ": "upsilon",
    "φ": "phi",
    "ϕ": "phi",
    "χ": "chi",
    "ψ": "psi",
    "ω": "omega",
}
_GREEK_NAMES.update({lower.upper(): name for lower, name in list(_GREEK_NAMES.items())})

# A comparison written as a word between spaces. Bare, the two characters
# are as likely to be a tag or a quotation mark as a comparison.
_SPACED_COMPARISON = re.compile(r"(?<=\s)([<>])(?=\s)")
_COMPARISON_WORDS = {"<": "less than", ">": "greater than"}

# A fraction the extraction wrote: a slash between a number or a fenced group
# and another. "kg/s" and "and/or" keep their slash.
_FRACTION_BAR = re.compile(r"(?<=[\d)])/(?=[\d(])")


def _group(text: str, start: int) -> tuple[str, int] | None:
    """The content of the braced group opening at `start` plus where it ends."""

    if start >= len(text) or text[start] != _OPEN:
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == _OPEN:
            depth += 1
        elif text[index] == _CLOSE:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    return None


def _script_at(text: str, start: int) -> tuple[str, str, int] | None:
    """A "_{...}" or "^{...}" opening at `start`: its mark, content and end."""

    if start >= len(text) or text[start] not in (_SUBSCRIPT, _SUPERSCRIPT):
        return None
    group = _group(text, start + 1)
    if group is None:
        return None
    content, end = group
    return text[start], content, end


def _power(exponent: str) -> str:
    word = _POWER_WORDS.get(exponent.strip())
    if word is not None:
        return f" {word} "
    return f" to the {exponent} "


def _limits(name: str, lower: str | None, upper: str | None) -> str:
    if lower is not None and upper is not None:
        return f" {name} from {lower} to {upper} of "
    if lower is not None:
        return f" {name} over {lower} of "
    return f" {name} to {upper} of "


def _expand(text: str) -> str:
    """Scripts and limits as words, nested groups expanded from the inside."""

    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        name = _LIMITED_OPERATORS.get(char)
        if name is not None:
            lower = upper = None
            end = index + 1
            while (script := _script_at(text, end)) is not None:
                mark, content, end = script
                if mark == _SUBSCRIPT:
                    lower = _expand(content)
                else:
                    upper = _expand(content)
            if lower is not None or upper is not None:
                out.append(_limits(name, lower, upper))
                index = end
                continue
        script = _script_at(text, index)
        if script is not None:
            mark, content, end = script
            inner = _expand(content)
            out.append(f" sub {inner} " if mark == _SUBSCRIPT else _power(inner))
            index = end
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _word_for(char: str) -> str:
    word = _SYMBOL_WORDS.get(char)
    if word is None:
        word = _GREEK_NAMES.get(char)
    if word is None:
        return char
    return f" {word} "


def speak_mathematics(text: str) -> str:
    """The text with its scripts, limits, symbols and Greek letters as words."""

    spoken = _expand(text)
    spoken = _SPACED_COMPARISON.sub(lambda m: _COMPARISON_WORDS[m.group(1)], spoken)
    spoken = _FRACTION_BAR.sub(" over ", spoken)
    spoken = "".join(_word_for(char) for char in spoken)
    return tidy_spacing(spoken)
