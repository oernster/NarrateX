"""Tests for saying a formula in words."""

from __future__ import annotations

from voice_reader.domain.services.spoken_mathematics import speak_mathematics


class TestLimits:
    def test_both_limits(self) -> None:
        out = speak_mathematics("N = ∑_{k = 0}^{m} d_{k}")

        assert out == "N equals the sum from k equals 0 to m of d sub k"

    def test_a_lower_limit_alone(self) -> None:
        assert speak_mathematics("∑_{k} x") == "the sum over k of x"

    def test_an_upper_limit_alone(self) -> None:
        assert speak_mathematics("∑^{∞} x") == "the sum to infinity of x"

    def test_an_operator_without_limits(self) -> None:
        assert speak_mathematics("∫ f") == "the integral of f"

    def test_a_limit_holding_a_script_of_its_own(self) -> None:
        out = speak_mathematics("∫_{t_{0}}^{t} f")

        assert out == "the integral from t sub 0 to t of f"

    def test_an_operator_whose_brace_never_closes_is_said_plainly(self) -> None:
        assert speak_mathematics("∑_{k").startswith("the sum of")


class TestScripts:
    def test_a_subscript_is_sub(self) -> None:
        assert speak_mathematics("M_{n}, x") == "M sub n, x"

    def test_nested_scripts_expand_from_the_inside(self) -> None:
        assert speak_mathematics("R_{O_{2}}") == "R sub O sub 2"

    def test_powers(self) -> None:
        assert speak_mathematics("x^{2}") == "x squared"
        assert speak_mathematics("x^{3}") == "x cubed"
        assert speak_mathematics("2^{17}") == "2 to the 17"

    def test_a_mark_without_a_group_is_left_alone(self) -> None:
        assert speak_mathematics("x_y") == "x_y"
        assert speak_mathematics("x_{y") == "x_{y"
        assert speak_mathematics("x_") == "x_"


class TestSymbols:
    def test_symbols_and_greek_letters_are_words(self) -> None:
        out = speak_mathematics("θ ≥ ΔD")

        assert out == "theta greater than or equal to delta D"

    def test_a_closing_fence_says_nothing(self) -> None:
        assert speak_mathematics("⌈n⌉ bits") == "the ceiling of n bits"

    def test_a_continuation_mark_says_nothing(self) -> None:
        assert speak_mathematics("↪x") == "x"

    def test_a_derivative_dot_is_said_after_its_letter(self) -> None:
        assert speak_mathematics("Ṁ_{CO}") == "M dot sub CO"

    def test_a_comparison_is_a_word_only_between_spaces(self) -> None:
        assert speak_mathematics("a < b") == "a less than b"
        assert speak_mathematics("<b>") == "<b>"

    def test_a_fraction_bar_is_over_but_a_unit_slash_is_not(self) -> None:
        assert speak_mathematics("1/((n − 1)!)") == "1 over ((n minus 1)!)"
        assert speak_mathematics("44/16") == "44 over 16"
        assert speak_mathematics("kg/mol") == "kg/mol"
