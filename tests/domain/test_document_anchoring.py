"""Tests for anchoring discovered blocks onto the canonical source text."""

from __future__ import annotations

import pytest

from voice_reader.domain.document.anchoring import BlockDraft, anchor_blocks
from voice_reader.domain.document.block_kind import BlockKind


def _draft(text: str, kind: BlockKind = BlockKind.PARAGRAPH, level: int = 0):
    return BlockDraft(kind=kind, text=text, level=level)


class TestBlockDraft:
    def test_rejects_a_kind_that_is_not_a_block_kind(self) -> None:
        with pytest.raises(TypeError):
            BlockDraft(kind="paragraph", text="x")  # type: ignore[arg-type]

    def test_rejects_a_negative_level(self) -> None:
        with pytest.raises(ValueError):
            BlockDraft(kind=BlockKind.HEADING, text="x", level=-1)


class TestAnchoring:
    def test_no_source_yields_no_blocks(self) -> None:
        assert anchor_blocks(source="", drafts=(_draft("x"),)) == ()

    def test_none_source_yields_no_blocks(self) -> None:
        assert anchor_blocks(source=None, drafts=(_draft("x"),)) == ()  # type: ignore[arg-type]

    def test_no_drafts_yields_no_blocks(self) -> None:
        assert anchor_blocks(source="some text", drafts=()) == ()

    def test_whitespace_only_source_yields_no_blocks(self) -> None:
        assert anchor_blocks(source="   \n\n  ", drafts=(_draft("x"),)) == ()

    def test_a_whitespace_only_draft_is_skipped(self) -> None:
        assert anchor_blocks(source="body", drafts=(_draft("   "),)) == ()

    def test_spans_index_the_source_exactly(self) -> None:
        source = "Chapter One\n\nThe opening line.\n"
        drafts = (
            _draft("Chapter One", BlockKind.HEADING, 1),
            _draft("The opening line."),
        )
        blocks = anchor_blocks(source=source, drafts=drafts)

        assert len(blocks) == 2
        for block, draft in zip(blocks, drafts):
            assert source[block.source_start : block.source_end] == draft.text

    def test_matching_ignores_differences_in_whitespace(self) -> None:
        # The source hard-wraps what the reader discovered as one paragraph.
        source = "The opening\nline of\nthe book."
        blocks = anchor_blocks(
            source=source,
            drafts=(_draft("The opening line of the book."),),
        )

        assert len(blocks) == 1
        assert blocks[0].source_start == 0
        assert blocks[0].source_end == len(source)

    def test_kind_and_level_are_carried_through(self) -> None:
        blocks = anchor_blocks(
            source="Chapter One",
            drafts=(_draft("Chapter One", BlockKind.HEADING, 2),),
        )

        assert blocks[0].kind is BlockKind.HEADING
        assert blocks[0].level == 2

    def test_an_unlocatable_draft_is_dropped(self) -> None:
        blocks = anchor_blocks(
            source="only this text",
            drafts=(_draft("only this text"), _draft("text that is absent")),
        )

        assert [b.text for b in blocks] == ["only this text"]

    def test_blocks_are_ordered_and_non_overlapping(self) -> None:
        source = "alpha beta gamma delta"
        drafts = (_draft("alpha"), _draft("beta"), _draft("gamma"), _draft("delta"))
        blocks = anchor_blocks(source=source, drafts=drafts)

        assert len(blocks) == 4
        for earlier, later in zip(blocks, blocks[1:]):
            assert earlier.source_end <= later.source_start

    def test_repeated_text_anchors_to_successive_occurrences(self) -> None:
        # A running header repeats on every page; each draft must land on its
        # own occurrence rather than all collapsing onto the first.
        source = "Header\npage one\nHeader\npage two"
        drafts = (
            _draft("Header", BlockKind.RUNNING_HEAD),
            _draft("page one"),
            _draft("Header", BlockKind.RUNNING_HEAD),
            _draft("page two"),
        )
        blocks = anchor_blocks(source=source, drafts=drafts)

        assert [b.source_start for b in blocks] == [0, 7, 16, 23]

    def test_scanning_is_forward_only(self) -> None:
        # "alpha" appears twice; a draft ordered after "beta" must anchor to
        # the later occurrence, never jump backwards.
        source = "alpha beta alpha"
        blocks = anchor_blocks(
            source=source,
            drafts=(_draft("beta"), _draft("alpha")),
        )

        assert [b.source_start for b in blocks] == [6, 11]

    def test_out_of_order_drafts_lose_the_ones_that_cannot_follow(self) -> None:
        # A draft that only exists before the cursor is dropped, not misplaced.
        source = "alpha beta"
        blocks = anchor_blocks(
            source=source,
            drafts=(_draft("beta"), _draft("alpha")),
        )

        assert [b.text for b in blocks] == ["beta"]

    def test_dropped_drafts_lower_the_confidence_signal(self) -> None:
        from voice_reader.domain.document.model import Document, Section

        source = "found text and much more prose that was never claimed"
        blocks = anchor_blocks(
            source=source,
            drafts=(_draft("found text"), _draft("absent text")),
        )
        section = Section(
            title="",
            source_start=0,
            source_end=len(source),
            blocks=blocks,
        )
        doc = Document(source_length=len(source), sections=(section,))

        assert len(blocks) == 1
        assert doc.displayed_ratio < 0.5


class TestFoldingWhatExtractionRewrites:
    """The extraction rewrites a few characters; matching has to mirror it.

    A PDF walk reports the characters the file actually contains, while
    `normalized_text` has already folded them. Without the same fold here, a
    draft is lost whole, so a single hyphen costs the paragraph around it.
    """

    def test_a_non_breaking_hyphen_matches_the_plain_one_in_the_source(self) -> None:
        # The source has been dehyphenated to ASCII; the draft has not.
        blocks = anchor_blocks(
            source="A decision-event changes the state.",
            drafts=(_draft("A decision‑event changes the state."),),
        )

        assert len(blocks) == 1
        assert blocks[0].source_start == 0
        assert blocks[0].source_end == len("A decision-event changes the state.")

    def test_a_soft_hyphen_in_a_draft_is_ignored(self) -> None:
        # Soft hyphens are invisible typesetting advice and are stripped from
        # the source, so a draft still carrying one must still match.
        blocks = anchor_blocks(
            source="Organisational structure.",
            drafts=(_draft("Organi­sational structure."),),
        )

        assert len(blocks) == 1
        assert blocks[0].source_end == len("Organisational structure.")

    def test_folding_keeps_spans_true_to_the_original_text(self) -> None:
        # Every fold is one character wide or dropped, so the offsets recorded
        # alongside still index the untouched source.
        source = "Intro.\n\nA latency-aware design.\n"
        blocks = anchor_blocks(
            source=source,
            drafts=(_draft("Intro."), _draft("A latency‑aware design.")),
        )

        assert len(blocks) == 2
        second = blocks[1]
        assert source[second.source_start : second.source_end] == (
            "A latency-aware design."
        )

    def test_a_draft_that_is_genuinely_absent_is_still_dropped(self) -> None:
        # Folding must widen what matches, never make matching approximate.
        assert (
            anchor_blocks(
                source="A decision-event.",
                drafts=(_draft("A different‑event."),),
            )
            == ()
        )
