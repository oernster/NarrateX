"""Tests for reading one row of a PDF's mathematics back as text.

Every geometry here is a hand-built span. The sizes and shifts are the ones
measured on a Word-produced book set in Cambria Math: a body of 10.9 points,
scripts of 8 and nested scripts of 6.5, a subscript two points below the
baseline and a superscript four above it. Rounded to a body of 10 here.
"""

from __future__ import annotations

from voice_reader.domain.document.pdf_mathematics import (
    COMPOSITE_FONT,
    PdfSpan,
    abuts,
    is_script,
    piece_from_span,
    render_group,
    render_level,
)

BODY = 10.0
SCRIPT = 8.0
NESTED = 6.5
BASELINE = 100.0
MATHS = "CambriaMath"
PROSE = "Cambria"


def span(
    text: str,
    left: float,
    right: float,
    baseline: float = BASELINE,
    *,
    size: float = BODY,
    font: str = MATHS,
    bold: bool = False,
    top: float | None = None,
    bottom: float | None = None,
) -> PdfSpan:
    return PdfSpan(
        text=text,
        font=font,
        size=size,
        bold=bold,
        left=left,
        top=baseline - 0.8 * size if top is None else top,
        right=right,
        bottom=baseline + 0.2 * size if bottom is None else bottom,
        baseline=baseline,
    )


def render(*pieces: PdfSpan) -> str:
    return render_level(list(pieces), baseline=BASELINE, size=BODY)


class TestPieces:
    def test_an_empty_span_is_no_piece(self) -> None:
        assert piece_from_span(span("", 0, 0)) is None

    def test_a_piece_carries_its_folded_text(self) -> None:
        piece = piece_from_span(span("\U0001d440=", 0, 10))

        assert piece is not None
        assert piece.text == "M = "

    def test_a_script_is_smaller_than_the_row_and_not_a_space(self) -> None:
        assert is_script(span("n", 0, 4, size=SCRIPT), size=BODY)
        assert not is_script(span("n", 0, 4, size=9.5), size=BODY)
        assert not is_script(span(" ", 0, 4, size=SCRIPT), size=BODY)

    def test_abutting_is_measured_against_the_following_piece(self) -> None:
        base = span("M", 0, 8)
        assert abuts(base, span("n", 9.5, 14, size=SCRIPT))
        assert not abuts(base, span("n", 10, 16, size=SCRIPT))


class TestSpacing:
    def test_a_gap_between_pieces_is_a_space(self) -> None:
        assert render(span("Let", 0, 15, font=PROSE), span("f", 20, 25)) == "Let f"

    def test_abutting_pieces_in_one_font_run_together(self) -> None:
        assert render(span("x", 0, 5), span("y", 5, 10)) == "xy"

    def test_a_variable_against_a_roman_word_is_two_words(self) -> None:
        out = render(span("D", 0, 6), span("independent", 6, 50, font=PROSE))

        assert out == "D independent"

    def test_a_word_against_a_bracket_stays_tight(self) -> None:
        out = render(span("cos", 0, 15, font=PROSE), span("(θ", 15, 25))

        assert out == "cos(θ"

    def test_a_space_piece_is_a_space(self) -> None:
        assert render(span("a", 0, 5), span(" ", 5, 8), span("b", 8, 13)) == "a b"

    def test_a_number_after_a_script_gets_a_space(self) -> None:
        out = render(
            span("d", 0, 5), span("k", 5, 8, 102, size=SCRIPT), span("3", 9, 14)
        )

        assert out == "d_{k}⋅3"


class TestScripts:
    def test_a_small_piece_below_the_baseline_is_a_subscript(self) -> None:
        assert render(span("M", 0, 8), span("n", 8, 12, 102, size=SCRIPT)) == "M_{n}"

    def test_a_small_piece_above_the_baseline_is_a_superscript(self) -> None:
        assert render(span("3", 0, 6), span("k", 6, 10, 96, size=SCRIPT)) == "3^{k}"

    def test_a_small_piece_on_the_baseline_is_small_text(self) -> None:
        out = render(
            span("M", 0, 8), span("min", 10, 20, 100.5, size=SCRIPT, font=PROSE)
        )

        assert out == "M min"

    def test_a_script_of_a_script_nests(self) -> None:
        out = render(
            span("R", 0, 7),
            span("O", 7, 12, 102, size=SCRIPT),
            span("2", 12, 15, 103.5, size=NESTED),
        )

        assert out == "R_{O_{2}}"

    def test_a_superscript_over_a_subscript_reads_subscript_first(self) -> None:
        out = render(
            span("M", 0, 8),
            span("min", 8, 20, 96, size=SCRIPT, font=PROSE),
            span("n", 8, 12, 102, size=SCRIPT),
        )

        assert out == "M_{n}^{min}"

    def test_scripts_in_sequence_keep_their_order(self) -> None:
        out = render(
            span("x", 0, 5),
            span("i", 5, 8, 102, size=SCRIPT),
            span("2", 9, 12, 96, size=SCRIPT),
        )

        assert out == "x_{i}^{2}"

    def test_a_subscript_beside_small_text_is_not_a_pair(self) -> None:
        out = render(
            span("x", 0, 5),
            span("i", 5, 8, 102, size=SCRIPT),
            span("j", 8, 11, 100.5, size=SCRIPT),
        )

        assert out == "x_{i}j"


class TestScriptFractions:
    def test_a_stack_standing_clear_of_the_row_is_a_fraction(self) -> None:
        out = render(
            span("+", 0, 5),
            span("1", 8, 12, 96, size=SCRIPT),
            span("2", 8, 12, 104, size=SCRIPT),
            span("O", 13, 20, font=PROSE),
        )

        assert out == "+ 1/2 O"

    def test_a_stack_opening_the_row_is_a_fraction(self) -> None:
        out = render(
            span("1", 0, 4, 96, size=SCRIPT), span("2", 0, 4, 104, size=SCRIPT)
        )

        assert out.strip() == "1/2"


class TestGroupsAndText:
    def test_a_group_is_read_at_the_size_of_its_largest_piece(self) -> None:
        out = render_group([span("a", 0, 4, 50, size=SCRIPT), span("b", 5, 10, 52)])

        assert out == "^{a}⋅b"


class TestFactorsAfterScripts:
    def test_a_counted_element_joins_the_next_with_nothing(self) -> None:
        out = render(
            span("H", 0, 6), span("2", 6, 9, 102, size=SCRIPT), span("O", 9, 15)
        )

        assert out == "H_{2}O"

    def test_a_factor_set_clear_of_the_script_stands_a_space_apart(self) -> None:
        out = render(
            span("x", 0, 5), span("i", 5, 8, 102, size=SCRIPT), span("y", 20, 25)
        )

        assert out == "x_{i} y"

    def test_a_rebuilt_fraction_after_a_script_takes_the_dot(self) -> None:
        out = render(
            span("x", 0, 5),
            span("i", 5, 8, 102, size=SCRIPT),
            span(" (a)/(b)", 8, 30, font=COMPOSITE_FONT),
        )

        assert out == "x_{i}⋅(a)/(b)"
