"""Tests for inline markdown stripping."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.markdown_inline import strip_inline


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("plain prose", "plain prose"),
        ("**bold**", "bold"),
        ("__bold__", "bold"),
        ("*italic*", "italic"),
        ("_italic_", "italic"),
        ("~~struck~~", "struck"),
        ("`code`", "code"),
        ("``code``", "code"),
        ("[text](https://example.com)", "text"),
        ("[text][ref]", "text"),
        ("![alt text](image.png)", "alt text"),
        ("a **bold** and *italic* mix", "a bold and italic mix"),
        ("**bold with *nested* italic**", "bold with nested italic"),
    ],
)
def test_strips_inline_syntax(source: str, expected: str) -> None:
    assert strip_inline(source) == expected


@pytest.mark.parametrize("source", ["", None])
def test_empty_input_yields_empty_output(source: str | None) -> None:
    assert strip_inline(source) == ""  # type: ignore[arg-type]


def test_leaves_snake_case_identifiers_alone() -> None:
    # Underscore emphasis must not fire inside a word.
    assert strip_inline("call build_toc_entries now") == "call build_toc_entries now"


def test_escaped_markers_survive_as_literals() -> None:
    assert strip_inline(r"\*not italic\*") == "*not italic*"


def test_escaped_backslash_survives() -> None:
    assert strip_inline(r"a \\ b") == r"a \ b"


def test_an_image_inside_a_link_prefers_the_alt_text() -> None:
    assert strip_inline("![cover](c.png)") == "cover"


def test_surrounding_whitespace_is_trimmed() -> None:
    assert strip_inline("   spaced   ") == "spaced"


def test_a_link_with_empty_text_strips_to_nothing() -> None:
    assert strip_inline("[]()") == ""
