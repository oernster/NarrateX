"""Tests for rebuilding a page's mathematics from the extractor's lines.

Geometry follows the measured book: a body of 10 points here, scripts of 8,
limits sixteen points over and fourteen under a summation sign, a numerator
eight points above the main row and a denominator seven below it.
"""

from __future__ import annotations

from voice_reader.domain.document.pdf_mathematics_layout import (
    PdfRawLine,
    assemble_lines,
)
from tests.domain.test_document_pdf_mathematics import (
    BASELINE,
    BODY,
    NESTED,
    PROSE,
    SCRIPT,
    span,
)


def line(*spans, block: int = 0, top: float | None = None, bottom: float | None = None):
    return PdfRawLine(
        spans=tuple(spans),
        block_index=block,
        top=min((s.top for s in spans), default=0.0) if top is None else top,
        bottom=(
            max((s.bottom for s in spans), default=0.0) if bottom is None else bottom
        ),
    )


def texts(*lines: PdfRawLine) -> list[str]:
    return [built.text for built in assemble_lines(tuple(lines))]


class TestPlainBlocks:
    def test_a_block_without_mathematics_passes_through_line_for_line(self) -> None:
        built = assemble_lines(
            (
                line(
                    span("Hello", 0, 20, font=PROSE, bold=True),
                    span(" ", 20, 23, font=PROSE),
                    span("world", 23, 40, font=PROSE, size=12.0),
                    top=1.0,
                    bottom=9.0,
                ),
                line(span("   ", 0, 5, font=PROSE)),
                line(block=1),
            )
        )

        assert [built.text for built in built] == ["Hello world", "   ", ""]
        assert (built[0].size, built[0].bold) == (12.0, True)
        assert (built[0].top, built[0].bottom) == (1.0, 9.0)
        assert built[2].size == 0.0
        assert [built.block_index for built in built] == [0, 0, 1]

    def test_styled_letters_fold_even_outside_a_maths_font(self) -> None:
        assert texts(line(span("\U0001d440", 0, 8, font=PROSE))) == ["M"]


class TestRows:
    def test_a_maths_block_of_nothing_but_space_yields_nothing(self) -> None:
        assert texts(line(span(" ", 0, 4))) == []

    def test_pieces_within_tolerance_share_a_row_and_lines_apart_do_not(self) -> None:
        together = texts(line(span("a", 0, 5), span("b", 8, 13, 102.5)))
        apart = texts(line(span("a", 0, 5)), line(span("b", 0, 5, 113)))

        assert together == ["a b"]
        assert apart == ["a", "b"]

    def test_a_tall_fence_off_the_baseline_stays_on_its_row(self) -> None:
        # Measured: a fence sits 0.31 of the size off its row.
        out = texts(
            line(
                span("n log", 0, 30, top=92, bottom=102),
                span("3⌉", 33, 40, 103.1, top=90, bottom=104),
            )
        )

        assert out == ["n log 3⌉"]

    def test_a_denominator_drawn_tall_is_not_on_the_main_row(self) -> None:
        """Page 96 of the measured book: the box of "32" reaches up into the
        main row; reading boxes rather than baselines lost the "88"."""

        out = texts(
            line(span("m =", 0, 20), span("88", 22, 34, 92.4, top=84, bottom=94)),
            line(
                span("32", 22, 34, 106.6, top=92, bottom=109),
                span("m", 36, 44),
                block=1,
            ),
        )

        assert out == ["m = 88/32 m"]

    def test_spaces_do_not_count_toward_the_row_size(self) -> None:
        """Page 47 of the measured book: "n + 1" padded with spaces once
        outweighed the body glyphs, so no script was found at all."""

        out = texts(
            line(
                span("H", 0, 8),
                span("n", 8, 12, 102, size=SCRIPT),
                span("↪H", 15, 30),
                span("n+1", 30, 44, 102, size=SCRIPT),
            )
        )

        assert out == ["H_{n} ↪ H_{n + 1}"]

    def test_a_line_holding_only_a_wrap_mark_is_dropped(self) -> None:
        out = texts(
            line(span("↪", 0, 4, 90, size=NESTED)),
            line(span("code", 0, 30, font=PROSE), block=1),
        )

        assert out == ["code"]

    def test_the_row_takes_the_baseline_of_its_widest_piece(self) -> None:
        # The fence's own baseline would read the subscript as small text.
        out = texts(
            line(
                span("⌈x", 0, 8, 103.5, top=90, bottom=104),
                span("long piece", 11, 60, top=92, bottom=102),
                span("k", 60, 64, 102, size=SCRIPT),
            )
        )

        assert out == ["⌈x long piece_{k}"]


class TestScriptPlacement:
    def test_a_script_set_against_its_base_belongs_with_it(self) -> None:
        out = texts(line(span("M", 0, 8), span("n", 8, 12, 102, size=SCRIPT)))

        assert out == ["M_{n}"]

    def test_a_script_overlapping_its_base_by_a_point_still_attaches(self) -> None:
        out = texts(
            line(
                span("R", 0, 7),
                span("O", 7, 12, 102, size=SCRIPT),
                span("2", 11.5, 15, 103.5, size=NESTED),
            )
        )

        assert out == ["R_{O_{2}}"]

    def test_a_script_against_an_operator_is_its_limit(self) -> None:
        out = texts(line(span("∑", 0, 8), span("k", 8, 12, 103, size=SCRIPT)))

        assert out == ["∑_{k}"]

    def test_limits_over_and_under_a_sign_are_found_across_blocks(self) -> None:
        out = texts(
            line(span("N =", 0, 20), top=92, bottom=102),
            line(span("m", 30, 36, 84, size=SCRIPT), block=1, top=78, bottom=86),
            line(span("∑", 28, 40), block=1, top=92, bottom=104),
            line(span("k=0", 28, 42, 114, size=SCRIPT), block=2, top=106, bottom=116),
            line(
                span("d", 45, 50),
                span("k", 50, 53, 102, size=SCRIPT),
                block=2,
                top=92,
                bottom=103,
            ),
        )

        assert out == ["N = ∑_{k = 0}^{m} d_{k}"]

    def test_a_limit_out_of_reach_falls_to_the_nearest_row(self) -> None:
        out = texts(
            line(span("x", 0, 5)),
            line(span("∑", 0, 8, 140)),
            line(span("m", 2, 6, 118, size=SCRIPT)),
        )

        assert out == ["x_{m}", "∑"]

    def test_the_nearest_operator_takes_a_limit_two_could_claim(self) -> None:
        out = texts(
            line(span("∑", 0, 8)),
            line(span("∫", 0, 8, 130)),
            line(span("m", 2, 6, 112, size=SCRIPT)),
        )

        assert out == ["∑_{m}", "∫"]

    def test_a_limit_beside_rather_than_over_a_sign_is_not_its_limit(self) -> None:
        # Not a limit, so it is read as a script of the row it is nearest to,
        # which here says the same thing by a different route.
        out = texts(line(span("∑", 0, 8)), line(span("m", 20, 24, 84, size=SCRIPT)))

        assert out == ["∑^{m}"]

    def test_a_space_follows_the_word_before_it_whatever_its_baseline(self) -> None:
        out = texts(
            line(span("a", 0, 5)),
            line(span(" ", 5, 8, 140)),
            line(span("b", 8, 13)),
        )

        assert out == ["a b"]

    def test_a_space_against_nothing_goes_to_the_nearest_row(self) -> None:
        assert texts(line(span("a", 0, 5)), line(span(" ", 20, 23, 140))) == ["a"]


class TestFractions:
    def test_a_row_above_and_below_a_gap_is_a_fraction(self) -> None:
        out = texts(
            line(span("I =", 0, 8), span("∫", 20, 28)),
            line(span("1", 10, 14, 92)),
            line(span("(n−1)!", 8, 18, 107)),
        )

        assert out == ["I = 1/((n − 1)!) ∫"]

    def test_a_fraction_may_open_the_row(self) -> None:
        out = texts(
            line(span("= x", 50, 60)),
            line(span("1", 10, 14, 92)),
            line(span("2", 10, 14, 107)),
        )

        assert out == ["1/2 = x"]

    def test_a_row_with_nothing_above_it_is_not_a_fraction(self) -> None:
        out = texts(line(span("x", 0, 5)), line(span("2", 0, 4, 107)))

        assert out == ["x", "2"]

    def test_a_gap_needs_both_halves(self) -> None:
        out = texts(
            line(span("x =", 0, 8), span("y", 20, 30)),
            line(span("1", 10, 14, 92)),
            line(span("2", 40, 44, 107)),
        )

        assert out == ["1", "x = y", "2"]

    def test_what_a_half_holds_outside_the_gap_stays_its_own_line(self) -> None:
        out = texts(
            line(span("x =", 0, 8)),
            line(span("1", 10, 14, 92)),
            line(span("2", 10, 14, 107), span("z", 40, 45, 107)),
        )

        assert out == ["x = 1/2", "z"]

    def test_a_script_left_on_a_consumed_row_reads_on_its_own(self) -> None:
        out = texts(
            line(span("x =", 0, 8)),
            line(span("1", 10, 14, 92)),
            line(span("2", 10, 14, 107)),
            line(span("q", 40, 43, 109, size=SCRIPT)),
        )

        assert out == ["x = 1/2", "q"]

    def test_a_space_left_on_a_consumed_row_is_nothing(self) -> None:
        out = texts(
            line(span("x =", 0, 8)),
            line(span("1", 10, 14, 92)),
            line(span("2", 10, 14, 107)),
            line(span(" ", 40, 43, 108)),
        )

        assert out == ["x = 1/2"]


class TestGrouping:
    def test_maths_blocks_that_do_not_overlap_are_rebuilt_apart(self) -> None:
        built = assemble_lines(
            (
                line(span("a", 0, 5), top=92, bottom=102),
                line(span("b", 0, 5, 118), block=1, top=105, bottom=120),
            )
        )

        assert [(b.text, b.block_index) for b in built] == [("a", 0), ("b", 1)]

    def test_a_script_sized_fragment_joins_across_a_small_gap(self) -> None:
        built = assemble_lines(
            (
                line(span("t", 20, 24, 84, size=SCRIPT), top=78, bottom=86),
                line(span("∫", 20, 28), block=1, top=89, bottom=102),
            )
        )

        assert [(b.text, b.block_index) for b in built] == [("∫^{t}", 0)]

    def test_a_group_is_emitted_where_its_first_block_stood(self) -> None:
        built = assemble_lines(
            (
                line(span("a", 0, 5), top=92, bottom=102),
                line(span("prose", 0, 30, font=PROSE), block=1),
                line(span("b", 10, 15), block=2, top=92, bottom=102),
            )
        )

        assert [(b.text, b.block_index) for b in built] == [("a b", 0), ("prose", 1)]

    def test_the_rebuilt_line_carries_its_evidence(self) -> None:
        (built,) = assemble_lines(
            (line(span("M", 0, 8, bold=True), span("n", 8, 12, 102, size=SCRIPT)),)
        )

        assert built.size == BODY
        assert built.bold is True
        assert built.top == BASELINE - 0.8 * BODY
        assert built.bottom == 102 + 0.2 * SCRIPT
