"""Tests for swapping EPUB MathML for its rendered notation."""

from __future__ import annotations

from bs4 import BeautifulSoup

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.mathml_notation import PRODUCT_DOT
from voice_reader.infrastructure.books import epub_mathematics, epub_structure

# Pandoc's markup for Euler's identity, inline, with its LaTeX annotation.
_EULER = (
    '<math display="inline" xmlns="http://www.w3.org/1998/Math/MathML">'
    "<semantics><mrow><msup><mi>e</mi><mrow><mi>i</mi><mi>π</mi></mrow></msup>"
    "<mo>+</mo><mn>1</mn><mo>=</mo><mn>0</mn></mrow>"
    '<annotation encoding="application/x-tex">e^{i\\pi}+1=0</annotation>'
    "</semantics></math>"
)
_SHOWN = f"e^{{i{PRODUCT_DOT}π}} + 1 = 0"


def test_each_formula_is_replaced_by_its_notation_and_its_source_dropped() -> None:
    soup = BeautifulSoup(f"<p>The identity {_EULER}.</p>", "lxml")

    assert epub_mathematics.replace_mathematics(soup) == 1
    assert soup.get_text() == f"The identity {_SHOWN}."


def test_an_upright_identifier_reads_as_a_word() -> None:
    upright = (
        "<math><msub><mi>P</mi><mrow><mi mathvariant='normal'>o</mi>"
        "<mi mathvariant='normal'>n</mi></mrow></msub></math>"
    )
    soup = BeautifulSoup(f"<p>{upright}</p>", "lxml")

    epub_mathematics.replace_mathematics(soup)

    assert soup.get_text() == "P_{on}"


def test_a_document_without_mathematics_is_untouched() -> None:
    soup = BeautifulSoup("<p>Plain prose.</p>", "lxml")

    assert epub_mathematics.replace_mathematics(soup) == 0
    assert soup.get_text() == "Plain prose."


def test_the_parsed_text_and_drafts_carry_the_notation() -> None:
    html = f"<html><body><h1>Rotations</h1><p>So {_EULER} holds.</p></body></html>"

    text, drafts = epub_structure.parse_html(html.encode("utf-8"))

    assert "\\pi" not in text
    assert _SHOWN in text
    assert [(d.kind, d.text) for d in drafts] == [
        (BlockKind.HEADING, "Rotations"),
        (BlockKind.PARAGRAPH, f"So {_SHOWN} holds."),
    ]
