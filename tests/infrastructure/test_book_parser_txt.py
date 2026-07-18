from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.books.parser import BookParser


def test_parser_txt_normalization(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("Hello\r\n\r\nWorld\t\t!", encoding="utf-8")
    parsed = BookParser().parse(p)
    raw, norm = parsed.raw_text, parsed.normalized_text
    assert "World" in raw
    assert norm == "Hello\n\nWorld !"


def test_parser_reads_markdown_as_markdown(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text(
        "# Chapter One\n\nThe opening **paragraph**\nwrapped over two lines.\n",
        encoding="utf-8",
    )

    parsed = BookParser().parse(p)

    assert parsed.document is not None
    blocks = parsed.document.blocks
    assert [b.text for b in blocks] == [
        "Chapter One",
        "The opening paragraph wrapped over two lines.",
    ]


def test_markdown_spans_index_the_normalized_text(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text("# Title\n\nSome prose here.\n", encoding="utf-8")

    parsed = BookParser().parse(p)

    for block in parsed.document.blocks:
        slice_ = parsed.normalized_text[block.source_start : block.source_end]
        assert block.text in slice_ or block.text.replace(" ", "") in slice_.replace(
            " ", ""
        )


def test_a_markdown_extension_variant_is_also_accepted(tmp_path: Path) -> None:
    p = tmp_path / "a.markdown"
    p.write_text("# Title\n\nProse.\n", encoding="utf-8")

    assert BookParser().parse(p).document is not None


def test_markdown_nesting_survives_normalisation(tmp_path: Path) -> None:
    # Leading indentation is how markdown states list nesting. Collapsing runs
    # of spaces, as prose normalisation does, would flatten it silently.
    p = tmp_path / "a.md"
    p.write_text("- outer\n  - inner\n    - deeper\n", encoding="utf-8")

    parsed = BookParser().parse(p)

    assert [b.level for b in parsed.document.blocks] == [1, 2, 3]


def test_markdown_normalisation_still_trims_and_collapses(tmp_path: Path) -> None:
    from voice_reader.infrastructure.books.parser import normalize_markdown_text

    assert normalize_markdown_text("a   \r\n\r\n\r\n\r\nb") == "a\n\nb"
