"""A heading's number and its title arrive as separate lines often enough.

Typesetting sets "8.1" above "From possibility to constraint", so extraction
reports two headings. Left apart, the number becomes a navigation entry that
says nothing and the title loses the number identifying it. On the reference
books rejoining them removed roughly a third of the sections outright.
"""

from __future__ import annotations

from voice_reader.domain.document.anchoring import anchor_blocks
from voice_reader.domain.document.block_kind import BlockKind
from voice_reader.domain.document.pdf_lines import PdfLine, drafts_from_lines

PAGE_HEIGHT = 800.0
BODY_SIZE = 10.0
HEADING_SIZE = BODY_SIZE * 2
MIDDLE = 400.0


def _line(
    text: str,
    *,
    size: float = BODY_SIZE,
    page: int = 0,
    block: int = 0,
) -> PdfLine:
    return PdfLine(
        text=text,
        size=size,
        bold=False,
        top=MIDDLE,
        bottom=MIDDLE + size,
        page_index=page,
        page_height=PAGE_HEIGHT,
        block_index=block,
    )


def _body(block: int) -> PdfLine:
    return _line("Ordinary body prose that anchors the body size. " * 3, block=block)


def _headings(drafts) -> list[str]:
    return [d.text for d in drafts if d.kind is BlockKind.HEADING]


class TestRejoiningNumbering:
    def test_a_number_on_its_own_line_joins_the_title_below_it(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("8.1", size=HEADING_SIZE, block=1),
                _line("From possibility to constraint", size=HEADING_SIZE, block=2),
                _body(3),
            )
        )

        assert "8.1 From possibility to constraint" in _headings(drafts)
        assert "8.1" not in _headings(drafts)

    def test_deeper_numbering_joins_too(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("3.1.1", size=HEADING_SIZE, block=1),
                _line("The illusion of uniqueness", size=HEADING_SIZE, block=2),
            )
        )

        assert "3.1.1 The illusion of uniqueness" in _headings(drafts)

    def test_a_trailing_dot_is_still_a_number(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("12.", size=HEADING_SIZE, block=1),
                _line("Latency", size=HEADING_SIZE, block=2),
            )
        )

        assert "12. Latency" in _headings(drafts)


class TestLeavingWellAlone:
    def test_a_heading_already_carrying_its_number_is_untouched(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("8.1 From possibility to constraint", size=HEADING_SIZE, block=1),
            )
        )

        assert _headings(drafts) == ["8.1 From possibility to constraint"]

    def test_a_number_followed_by_body_text_is_kept_as_it_was(self) -> None:
        # Nothing to join it to, so it stays rather than being swallowed.
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("8.1", size=HEADING_SIZE, block=1),
                _body(2),
            )
        )

        assert "8.1" in _headings(drafts)

    def test_two_numbers_in_a_row_keep_the_first(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("8.1", size=HEADING_SIZE, block=1),
                _line("8.2", size=HEADING_SIZE, block=2),
                _line("Definition", size=HEADING_SIZE, block=3),
            )
        )

        assert _headings(drafts) == ["8.1", "8.2 Definition"]

    def test_a_number_at_the_very_end_survives(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("8.1", size=HEADING_SIZE, block=1),
            )
        )

        assert "8.1" in _headings(drafts)


class TestWrappedHeadings:
    """A heading wraps like a paragraph does.

    Taking a heading a line at a time left the second half as a section of its
    own, starting mid-sentence or, where the break was hyphenated, mid-word.
    The chapter list showed entries reading "uct Roadmap" and "mental".
    """

    def test_a_heading_split_across_lines_becomes_one(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line(
                    "Chapter 1: Decision objects and the", size=HEADING_SIZE, block=1
                ),
                _line("shape of organisational systems", size=HEADING_SIZE, block=1),
            )
        )

        assert _headings(drafts) == [
            "Chapter 1: Decision objects and the shape of organisational systems"
        ]

    def test_a_hyphenated_break_in_a_heading_heals(self) -> None:
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("Chapter 26: An Unstable Prod-", size=HEADING_SIZE, block=1),
                _line("uct Roadmap", size=HEADING_SIZE, block=1),
            )
        )

        assert _headings(drafts) == ["Chapter 26: An Unstable Product Roadmap"]

    def test_separate_headings_stay_separate(self) -> None:
        # Different groupings from the extractor, so two real headings.
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("Chapter 1", size=HEADING_SIZE, block=1),
                _line("Chapter 2", size=HEADING_SIZE, block=2),
            )
        )

        assert _headings(drafts) == ["Chapter 1", "Chapter 2"]

    def test_headings_of_different_ranks_stay_separate(self) -> None:
        # Same grouping but a different size, so a title and its subtitle.
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("Book One", size=HEADING_SIZE * 2, block=1),
                _line("Decision Architecture", size=HEADING_SIZE, block=1),
            )
        )

        assert _headings(drafts) == ["Book One", "Decision Architecture"]

    def test_furniture_between_headings_does_not_merge(self) -> None:
        # A folio is a line in its own right and never wraps.
        drafts = drafts_from_lines(
            (
                _body(0),
                _line("Chapter 1", size=HEADING_SIZE, block=1),
                _line("42", block=1, page=0),
                _line("Chapter 2", size=HEADING_SIZE, block=1),
            )
        )

        assert _headings(drafts) == ["Chapter 1", "Chapter 2"]


class TestStillAnchors:
    def test_a_rejoined_heading_finds_itself_in_the_source(self) -> None:
        """Rejoining must not cost the block its place in the canonical text.

        The source keeps the two on separate lines. Matching ignores
        whitespace, so the joined form still resolves, and its span has to
        cover both lines rather than only the title.
        """

        opening = "Ordinary body prose, set long enough to fix the body size."
        source = f"{opening}\n8.1\nFrom possibility to constraint\nMore prose.\n"
        drafts = drafts_from_lines(
            (
                _line(opening, block=0),
                _line("8.1", size=HEADING_SIZE, block=1),
                _line("From possibility to constraint", size=HEADING_SIZE, block=2),
                _line("More prose.", block=3),
            )
        )

        blocks = anchor_blocks(source=source, drafts=drafts)
        headings = [b for b in blocks if b.kind is BlockKind.HEADING]

        assert len(headings) == 1
        heading = headings[0]
        assert source[heading.source_start] == "8"
        assert source[heading.source_start : heading.source_end] == (
            "8.1\nFrom possibility to constraint"
        )
