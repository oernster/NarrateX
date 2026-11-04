"""Tests for writing MathML presentation markup in the plain notation.

Every tree is the shape pandoc writes for the LaTeX in each test's name, read
off a pandoc-built book's own markup.
"""

from __future__ import annotations

from voice_reader.domain.document.mathml_notation import (
    PRODUCT_DOT,
    MathNode,
    render_mathml,
)

DOT = PRODUCT_DOT


def mi(text: str, *, upright: bool = False) -> MathNode:
    return MathNode(tag="mi", text=text, upright=upright)


def mn(text: str) -> MathNode:
    return MathNode(tag="mn", text=text)


def mo(text: str) -> MathNode:
    return MathNode(tag="mo", text=text)


def node(tag: str, *children: MathNode) -> MathNode:
    return MathNode(tag=tag, children=children)


def row(*children: MathNode) -> MathNode:
    return node("mrow", *children)


def math(*children: MathNode) -> str:
    return render_mathml(node("math", node("semantics", row(*children))))


def function(name: str) -> MathNode:
    return row(mi(name, upright=True), mo("⁡"))


class TestProducts:
    def test_euler_writes_its_implicit_product_with_a_dot(self) -> None:
        exponent = row(mi("i"), mi("π"))
        out = math(node("msup", mi("e"), exponent), mo("+"), mn("1"), mo("="), mn("0"))

        assert out == f"e^{{i{DOT}π}} + 1 = 0"

    def test_a_function_name_is_spaced_from_its_argument_not_dotted(self) -> None:
        out = math(
            function("cos"),
            mi("θ"),
            mo("+"),
            mi("i"),
            function("sin"),
            mi("θ"),
        )

        assert out == "cos θ + i sin θ"

    def test_a_scripted_function_keeps_its_script(self) -> None:
        log = node("msub", function("log"), mn("2"))

        assert math(mo("⌈"), mi("n"), log, mn("3"), mo("⌉")) == ("⌈n log_{2} 3⌉")

    def test_a_bare_multi_letter_identifier_is_a_function(self) -> None:
        assert math(mi("ln"), mn("2")) == "ln 2"

    def test_a_number_before_a_variable_and_a_scripted_term_take_a_dot(self) -> None:
        term = node("msub", mi("d"), mi("k"))
        power = node("msup", mn("3"), mi("k"))

        assert math(term, power) == f"d_{{k}}{DOT}3^{{k}}"
        assert math(mn("2"), mi("π")) == f"2{DOT}π"

    def test_a_group_after_an_operand_takes_a_dot(self) -> None:
        assert math(mi("C"), mo("("), mi("t"), mo(")")) == "C(t)"
        fraction = node("mfrac", mi("a"), mi("b"))
        assert math(mi("x"), fraction) == f"x{DOT}a/b"

    def test_an_operand_before_a_closing_fence_takes_no_dot(self) -> None:
        closing = node("msup", mo(")"), mi("D"))

        assert math(mo("("), mi("Z"), closing) == "(Z)^{D}"

    def test_the_invisible_times_sign_is_the_dot(self) -> None:
        assert math(mi("a"), mo("⁢"), mi("b")) == f"a{DOT}b"


class TestExemptions:
    def test_a_differential_opening_a_term_takes_no_dot(self) -> None:
        out = math(mi("f"), mo("("), mi("s"), mo(")"), node("mspace"), mi("d"), mi("s"))

        assert out == "f(s) ds"

    def test_a_differential_opening_a_fraction_takes_no_dot(self) -> None:
        top = row(mi("d"), node("msub", mi("I"), mi("n")))
        bottom = row(mi("d"), mi("t"))

        assert math(node("mfrac", top, bottom)) == "dI_{n}/dt"

    def test_a_d_after_an_operand_is_a_factor(self) -> None:
        assert math(mi("a"), mi("d"), mi("t")) == f"a{DOT}d{DOT}t"

    def test_a_prefix_operator_takes_no_dot(self) -> None:
        change = row(mi("Δ"), node("msub", mi("D"), mi("n")))

        assert math(change) == "ΔD_{n}"
        assert math(mi("∂"), node("msub", mi("f"), mi("i"))) == "∂f_{i}"

    def test_neighbouring_indices_in_a_subscript_are_not_a_product(self) -> None:
        out = math(node("msub", mi("J"), row(mi("i"), mi("j"))))

        assert out == "J_{ij}"

    def test_an_italic_chemical_formula_takes_no_dot(self) -> None:
        oxide = node("msub", mi("O"), mn("2"))

        assert math(mn("2"), mi("C"), oxide) == "2CO_{2}"
        assert math(mi("C"), mi("O")) == "CO"

    def test_a_variable_with_a_letter_subscript_is_not_chemistry(self) -> None:
        gas = node("msub", mi("R"), mi("g"))

        assert math(gas, mi("T")) == f"R_{{g}}{DOT}T"

    def test_an_upright_word_is_the_word_it_spells(self) -> None:
        word = [mi(letter, upright=True) for letter in "available"]

        assert math(node("msub", mi("P"), row(*word))) == "P_{available}"

    def test_an_upright_chemical_formula_takes_no_dot(self) -> None:
        oxide = node("msub", mi("O", upright=True), mn("2"))

        assert math(mn("2"), mi("C", upright=True), oxide) == "2CO_{2}"

    def test_a_compound_operand_stands_apart_from_the_word_after_it(self) -> None:
        half = node("mfrac", mn("1"), mn("2"))
        oxygen = node("msub", mi("O", upright=True), mn("2"))

        assert math(half, oxygen) == "1/2 O_{2}"
        assert math(mi("Λ"), mi("C", upright=True), mi("D", upright=True)) == ("ΛCD")

    def test_an_upright_letter_outside_ascii_is_still_a_variable(self) -> None:
        assert math(mi("π", upright=True), mi("r")) == f"π{DOT}r"


class TestOperators:
    def test_relations_are_spaced_and_signs_only_when_binary(self) -> None:
        out = math(mi("x"), mo("∈"), mo("{"), mi("−"), mn("1"), mo("}"))

        assert out == "x ∈ {−1}"
        assert math(mi("a"), mi("+"), mi("b")) == "a + b"

    def test_a_sign_after_a_word_or_a_closing_fence_is_binary(self) -> None:
        assert math(MathNode(tag="mtext", text="cost"), mo("+"), mn("1")) == "cost + 1"
        assert math(mo("("), mi("a"), mo(")"), mo("−"), mi("b")) == "(a) − b"

    def test_pandoc_spellings_are_read_as_the_signs_they_stand_for(self) -> None:
        assert math(mi("A"), mo("\\"), mi("B")) == "A ∖ B"
        assert math(mi("a"), mo("-"), mi("b")) == "a − b"

    def test_a_negated_arrow_is_composed(self) -> None:
        assert math(mi("p"), mo("⇏"), mi("q")) == "p ⇏ q"

    def test_commas_separate_except_inside_a_number(self) -> None:
        assert math(mn("177"), mo(","), mn("147")) == "177,147"
        assert math(mn("1"), mo(","), mn("2")) == "1, 2"
        assert math(mi("a"), mo(";"), mi("b")) == "a; b"

    def test_a_big_operator_is_spaced_from_what_follows(self) -> None:
        integral = node("msubsup", mo("∫"), mi("a"), mi("b"))

        assert math(integral, mo("("), mi("x"), mo(")")) == "∫_{a}^{b} (x)"
        assert math(mo("∑"), mi("x")) == "∑ x"

    def test_nothing_is_set_after_an_opening_fence(self) -> None:
        assert math(mo("("), function("cos"), mi("x"), mo(")")) == "(cos x)"


class TestScriptsAndLimits:
    def test_limits_over_and_under_a_big_operator(self) -> None:
        total = node("munderover", mo("∑"), row(mi("k"), mo("="), mn("0")), mi("m"))

        assert math(total, mi("x")) == "∑_{k = 0}^{m} x"
        assert math(node("munder", mo("∑"), mi("k")), mi("x")) == "∑_{k} x"

    def test_a_dot_accent_sets_on_its_letter(self) -> None:
        rate = node("msub", node("mover", mi("M"), mo("̇")), mi("O"))

        assert math(rate) == "Ṁ_{O}"

    def test_an_over_script_that_is_no_accent_is_a_superscript(self) -> None:
        assert math(node("mover", mi("x"), mi("k"))) == "x^{k}"
        assert math(node("munder", mi("x"), mi("k"))) == "x_{k}"

    def test_a_subscript_and_superscript_together(self) -> None:
        assert math(node("msubsup", mi("E"), mi("t"), mi("H"))) == "E_{t}^{H}"


class TestOtherElements:
    def test_a_fraction_fences_compound_halves(self) -> None:
        out = math(node("mfrac", mn("1"), row(mo("("), mi("n"), mo(")"), mo("!"))))

        assert out == "1/((n)!)"

    def test_roots(self) -> None:
        assert math(node("msqrt", mi("x"))) == "√(x)"
        assert math(node("mroot", mi("x"), mn("3"))) == "√^{3}(x)"

    def test_a_matrix_reads_row_by_row(self) -> None:
        table = node(
            "mtable",
            node("mtr", node("mtd", mi("a")), node("mtd", mi("b"))),
            node("mtr", node("mtd", mi("c")), node("mtd", MathNode(tag="mtd"))),
        )

        assert math(mo("["), table, mo("]")) == "[a, b; c]"

    def test_silent_elements_and_spaces_say_nothing(self) -> None:
        source = MathNode(tag="annotation", text="e^{i\\pi}")

        assert render_mathml(node("semantics", row(mi("x")), source)) == "x"
        assert math(mi("a"), node("mphantom", mi("b")), mi("c")) == f"a{DOT}c"
        assert render_mathml(node("semantics")) == ""

    def test_a_text_run_and_a_box_read_as_written(self) -> None:
        boxed = node("menclose", MathNode(tag="mtext", text="issuer"))

        assert math(boxed) == "issuer"

    def test_an_unknown_element_reads_its_children_or_its_text(self) -> None:
        assert math(node("mfenced", mi("a"), mi("b"))) == f"a{DOT}b"
        assert math(MathNode(tag="ms", text="q")) == "q"
