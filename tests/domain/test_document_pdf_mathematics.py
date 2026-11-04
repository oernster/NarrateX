"""Tests for reading one row of a PDF's mathematics back as text.

Every geometry here is a hand-built span. The sizes and shifts are the ones
measured on a Word-produced book set in Cambria Math: a body of 10.9 points,
scripts of 8 and nested scripts of 6.5, a subscript two points below the
baseline and a superscript four above it. Rounded to a body of 10 here.
"""

from __future__ import annotations

from voice_reader.domain.document.pdf_mathematics import (
    PdfSpan,
    abuts,
    fold_text,
    fraction_text,
    is_relation,
    is_script,
    piece_from_span,
    render_group,
    render_level,
    tidy_spacing,
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


class TestFoldText:
    def test_styled_letters_fold_to_plain_ones_in_any_font(self) -> None:
        assert fold_text("\U0001d440\U0001d45b", maths=False) == "Mn"
        assert fold_text("\U0001d703", maths=True) == "θ"

    def test_letterlike_set_symbols_fold_but_a_trade_mark_sign_does_not(self) -> None:
        assert fold_text("ℕℎ", maths=False) == "Nh"
        assert fold_text("™", maths=False) == "™"

    def test_unmapped_glyphs_are_read_only_in_a_maths_font(self) -> None:
        assert fold_text("෍නൣ൧", maths=True) == "∑∫()"
        assert fold_text("෍", maths=False) == "෍"

    def test_relations_are_padded_only_in_a_maths_font(self) -> None:
        assert fold_text("N=", maths=True) == "N = "
        assert fold_text("d∈{", maths=True) == "d ∈ {"
        assert fold_text("N=", maths=False) == "N="

    def test_a_sign_is_padded_only_where_it_is_binary(self) -> None:
        assert fold_text("θ+", maths=True) == "θ + "
        assert fold_text("(t−s)", maths=True) == "(t − s)"
        assert fold_text("{−1", maths=True) == "{−1"

    def test_a_combining_mark_set_before_its_letter_moves_after_it(self) -> None:
        assert fold_text("̇M", maths=True) == "Ṁ"


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

        assert out == "d_{k} 3"


class TestScripts:
    def test_a_small_piece_below_the_baseline_is_a_subscript(self) -> None:
        assert render(span("M", 0, 8), span("n", 8, 12, 102, size=SCRIPT)) == "M_{n}"

    def test_a_small_piece_above_the_baseline_is_a_superscript(self) -> None:
        assert render(span("3", 0, 6), span("k", 6, 10, 96, size=SCRIPT)) == "3^{k}"

    def test_a_small_piece_on_the_baseline_is_small_text(self) -> None:
        out = render(span("M", 0, 8), span("min", 10, 20, 100.5, size=SCRIPT))

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
            span("min", 8, 20, 96, size=SCRIPT),
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
            span("O", 13, 20),
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

        assert out == "^{a} b"

    def test_a_fraction_fences_anything_but_an_atom(self) -> None:
        assert fraction_text("1", "(n − 1)!") == "1/((n − 1)!)"
        assert fraction_text("28", "16") == "28/16"
        assert fraction_text("a b", "c") == "(a b)/c"

    def test_a_relation_is_one_relation_sign(self) -> None:
        assert is_relation("=") and is_relation("↪")
        assert not is_relation("+") and not is_relation("==")

    def test_tidy_spacing_collapses_and_trims(self) -> None:
        assert tidy_spacing("  a  b , c . ") == "a b, c."
