"""Tests for the characters of written mathematics, shared by both readers."""

from __future__ import annotations

from voice_reader.domain.document.maths_notation_text import (
    fold_text,
    fraction_text,
    is_relation,
    tidy_spacing,
)


class TestFoldText:
    def test_styled_letters_fold_to_plain_ones_in_any_font(self) -> None:
        assert fold_text("\U0001d440\U0001d45b", maths=False) == "Mn"
        assert fold_text("\U0001d703", maths=True) == "θ"

    def test_letterlike_set_symbols_fold_but_a_trade_mark_sign_does_not(self) -> None:
        assert fold_text("ℕℎ", maths=False) == "Nh"
        assert fold_text("™", maths=False) == "™"

    def test_unmapped_glyphs_are_read_only_in_a_maths_font(self) -> None:
        assert fold_text("෍නൣ൧", maths=True) == "∑ ∫ ()"
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


class TestNotation:
    def test_a_fraction_fences_anything_but_an_atom(self) -> None:
        assert fraction_text("1", "(n − 1)!") == "1/((n − 1)!)"
        assert fraction_text("28", "16") == "28/16"
        assert fraction_text("a b", "c") == "(a b)/c"

    def test_a_relation_is_one_relation_sign(self) -> None:
        assert is_relation("=") and is_relation("↪")
        assert not is_relation("+") and not is_relation("==")

    def test_tidy_spacing_collapses_and_trims(self) -> None:
        assert tidy_spacing("  a  b , c . ") == "a b, c."
