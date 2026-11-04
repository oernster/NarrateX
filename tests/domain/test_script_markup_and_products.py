"""Tests for finding script markers and for marking implicit products."""

from __future__ import annotations

from voice_reader.domain.document.product_marks import (
    PRODUCT_DOT,
    is_chemical_join,
    joins_as_product,
    mark_products,
)
from voice_reader.domain.document.script_markup import ScriptKind, script_runs

MARK = ScriptKind.MARKER
SUB = ScriptKind.SUBSCRIPT
SUP = ScriptKind.SUPERSCRIPT


def described(text: str) -> list[tuple[str, ScriptKind, tuple[ScriptKind, ...]]]:
    return [(text[r.start : r.end], r.kind, r.shifts) for r in script_runs(text)]


class TestScriptRuns:
    def test_a_subscript_is_a_marker_its_content_and_a_closing_marker(self) -> None:
        assert described("O_{2}") == [
            ("_{", MARK, ()),
            ("2", SUB, (SUB,)),
            ("}", MARK, ()),
        ]

    def test_nested_scripts_list_the_outer_then_the_inner(self) -> None:
        runs = described("ω^{d_{k}}")

        assert ("d_{k}", SUP, (SUP,)) in runs
        assert ("k", SUB, (SUP, SUB)) in runs
        assert [r for r in runs if r[1] is MARK] == [
            ("^{", MARK, ()),
            ("_{", MARK, ()),
            ("}", MARK, ()),
            ("}", MARK, ()),
        ]

    def test_a_marker_needs_a_base_and_a_closing_brace(self) -> None:
        assert described("a _{b}") == []
        assert described("_{b}") == []
        assert described("x_{b") == []
        assert described("x_b") == []

    def test_a_group_closing_past_the_range_is_left_alone(self) -> None:
        assert script_runs("x_{2} y", 0, 4) == ()
        assert [r.kind for r in script_runs("p x_{2}", 2)] == [MARK, SUB, MARK]


class TestProducts:
    def test_neighbouring_variables_take_the_dot(self) -> None:
        assert mark_products("iπ") == f"i{PRODUCT_DOT}π"
        assert mark_products("2πi") == f"2{PRODUCT_DOT}π{PRODUCT_DOT}i"

    def test_the_five_exemptions_take_no_dot(self) -> None:
        assert mark_products("ΔD") == "ΔD"
        assert mark_products("dt") == "dt"
        assert mark_products("x ds") == "x ds"
        assert mark_products("2CO") == "2CO"
        assert mark_products("a = b") == "a = b"

    def test_a_d_after_a_variable_is_a_factor(self) -> None:
        assert mark_products("ad") == f"a{PRODUCT_DOT}d"
        assert joins_as_product("a", "d", "t")

    def test_a_number_after_a_letter_is_not_a_new_factor(self) -> None:
        assert not joins_as_product("", "x", "2")

    def test_two_capitals_join_as_chemistry(self) -> None:
        assert is_chemical_join("H", "O")
        assert not is_chemical_join("g", "T")
