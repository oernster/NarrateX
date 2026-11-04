"""Replace each MathML formula in an EPUB document with its plain notation.

BeautifulSoup flattens a `<math>` element as every token it holds, spaced
apart, followed by the LaTeX annotation it was built from. Swapping each
element for one string of the rendered presentation tree, before anything
reads the text, means the canonical text and the drafts both carry the
formula as a reader sees it. A document with no `<math>` is left untouched.
"""

from __future__ import annotations

from voice_reader.domain.document.mathml_notation import MathNode, render_mathml

_UPRIGHT = "normal"


def _node(element) -> MathNode:
    name = str(element.name).lower()
    children = tuple(
        _node(child) for child in element.children if getattr(child, "name", None)
    )
    return MathNode(
        tag=name,
        text="" if children else element.get_text(),
        upright=element.get("mathvariant") == _UPRIGHT,
        children=children,
    )


def replace_mathematics(soup) -> int:
    """Swap every `<math>` element for its rendered text; the count replaced."""

    formulas = soup.find_all("math")
    for element in formulas:
        element.replace_with(render_mathml(_node(element)))
    return len(formulas)
