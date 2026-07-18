"""Tests for recovering block structure from EPUB XHTML."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.infrastructure.books import epub_structure

bs4 = pytest.importorskip("bs4")


def _soup(html: str):
    return bs4.BeautifulSoup(html.encode("utf-8"), "html.parser")


def _drafts(html: str):
    return epub_structure.drafts_from_soup(_soup(html))


class TestHeadings:
    def test_heading_tags_carry_their_level(self) -> None:
        drafts = _drafts("<h1>One</h1><h2>Two</h2><h3>Three</h3>")

        assert [(d.text, d.level) for d in drafts] == [
            ("One", 1),
            ("Two", 2),
            ("Three", 3),
        ]
        assert all(d.kind is BlockKind.HEADING for d in drafts)

    def test_all_six_heading_levels_are_recognised(self) -> None:
        html = "".join(f"<h{n}>H{n}</h{n}>" for n in range(1, 7))
        drafts = _drafts(html)

        assert [d.level for d in drafts] == [1, 2, 3, 4, 5, 6]


class TestBlockKinds:
    def test_paragraphs_become_paragraph_drafts(self) -> None:
        drafts = _drafts("<p>Some prose.</p>")

        assert drafts[0].kind is BlockKind.PARAGRAPH
        assert drafts[0].text == "Some prose."

    def test_list_items_become_list_item_drafts(self) -> None:
        drafts = _drafts("<ul><li>one</li><li>two</li></ul>")

        assert [d.kind for d in drafts] == [BlockKind.LIST_ITEM] * 2
        assert [d.text for d in drafts] == ["one", "two"]

    def test_nested_lists_increase_the_level(self) -> None:
        drafts = _drafts("<ul><li>outer</li><ul><li>inner</li></ul></ul>")

        assert [d.level for d in drafts] == [1, 2]

    def test_preformatted_text_becomes_code(self) -> None:
        drafts = _drafts("<pre>x = 1</pre>")

        assert drafts[0].kind is BlockKind.CODE

    def test_block_quotes_become_quote_drafts(self) -> None:
        drafts = _drafts("<blockquote><p>Quoted words.</p></blockquote>")

        assert [d.kind for d in drafts] == [BlockKind.BLOCK_QUOTE]
        assert drafts[0].text == "Quoted words."

    def test_document_order_is_preserved(self) -> None:
        drafts = _drafts("<h1>Title</h1><p>First.</p><p>Second.</p>")

        assert [d.text for d in drafts] == ["Title", "First.", "Second."]


class TestNesting:
    def test_a_nested_block_is_emitted_once_at_the_outermost_level(self) -> None:
        # The paragraph belongs to the quote and must not be emitted twice.
        drafts = _drafts("<blockquote><p>Inside the quote.</p></blockquote>")

        assert len(drafts) == 1
        assert drafts[0].kind is BlockKind.BLOCK_QUOTE

    def test_inline_markup_inside_a_block_is_flattened_into_its_text(self) -> None:
        drafts = _drafts("<p>A <em>stressed</em> word.</p>")

        assert drafts[0].text == "A stressed word."

    def test_empty_elements_are_skipped(self) -> None:
        drafts = _drafts("<p></p><p>   </p><p>Real text.</p>")

        assert [d.text for d in drafts] == ["Real text."]

    def test_unknown_tags_are_ignored(self) -> None:
        drafts = _drafts("<div>Wrapper</div><p>Real text.</p>")

        assert [d.text for d in drafts] == ["Real text."]


class TestParseHtml:
    def test_returns_text_and_drafts(self) -> None:
        result = epub_structure.parse_html(b"<h1>Title</h1><p>Body text.</p>")

        assert result is not None
        text, drafts = result
        assert "Title" in text
        assert "Body text." in text
        assert [d.kind for d in drafts] == [BlockKind.HEADING, BlockKind.PARAGRAPH]

    def test_text_matches_the_previous_flattening_exactly(self) -> None:
        # The extracted text is the coordinate system for every persisted
        # offset, so it must not shift when structure is recovered.
        html = b"<h1>Title</h1><p>Body <em>text</em>.</p>"
        soup = bs4.BeautifulSoup(html, "html.parser")
        expected = (soup.get_text("\n", strip=True) or "").strip()

        result = epub_structure.parse_html(html)

        assert result is not None
        assert result[0] == expected

    def test_returns_none_when_the_html_parser_is_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import sys

        monkeypatch.setitem(sys.modules, "bs4", None)

        assert epub_structure.parse_html(b"<p>x</p>") is None

    def test_falls_back_to_the_builtin_parser_when_lxml_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real = bs4.BeautifulSoup
        calls: list[str] = []

        def fake(markup, parser):
            calls.append(parser)
            if parser == "lxml":
                raise RuntimeError("lxml unavailable")
            return real(markup, parser)

        monkeypatch.setattr(bs4, "BeautifulSoup", fake)

        result = epub_structure.parse_html(b"<p>Body.</p>")

        assert calls == ["lxml", "html.parser"]
        assert result is not None
        assert result[0] == "Body."
