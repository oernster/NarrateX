"""Tests for assembling a document from format-supplied drafts."""

from __future__ import annotations

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.assembly import build_from_drafts
from voice_reader.domain.document.block_kind import BlockKind

SOURCE = (
    "Chapter One\n"
    "\n"
    "The opening paragraph of the book.\n"
    "\n"
    "Chapter Two\n"
    "\n"
    "The closing paragraph of the book.\n"
)

DRAFTS = (
    BlockDraft(kind=BlockKind.HEADING, text="Chapter One", level=1),
    BlockDraft(kind=BlockKind.PARAGRAPH, text="The opening paragraph of the book."),
    BlockDraft(kind=BlockKind.HEADING, text="Chapter Two", level=1),
    BlockDraft(kind=BlockKind.PARAGRAPH, text="The closing paragraph of the book."),
)


def test_empty_source_yields_an_empty_document() -> None:
    doc = build_from_drafts(source="", drafts=DRAFTS)

    assert doc.source_length == 0
    assert doc.sections == ()


def test_none_source_is_treated_as_empty() -> None:
    doc = build_from_drafts(source=None, drafts=DRAFTS)  # type: ignore[arg-type]

    assert doc.source_length == 0


def test_no_drafts_yields_a_document_with_no_sections() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=())

    assert doc.source_length == len(SOURCE)
    assert doc.sections == ()


def test_source_length_matches_the_source() -> None:
    assert build_from_drafts(source=SOURCE, drafts=DRAFTS).source_length == len(SOURCE)


def test_drafts_become_sections_split_at_headings() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=DRAFTS)

    assert [s.title for s in doc.sections] == ["Chapter One", "Chapter Two"]


def test_contents_are_derived_and_resolved() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=DRAFTS)

    assert [e.title for e in doc.toc] == ["Chapter One", "Chapter Two"]
    assert all(e.is_resolved for e in doc.toc)


def _same_ignoring_whitespace(left: str, right: str) -> bool:
    return "".join(left.split()) == "".join(right.split())


def test_every_block_is_anchored_into_the_source() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=DRAFTS)

    for block in doc.blocks:
        slice_ = SOURCE[block.source_start : block.source_end]
        assert _same_ignoring_whitespace(slice_, block.text)


def test_anchoring_survives_a_source_that_wraps_mid_block() -> None:
    # The real case: the source hard-wraps, while the reader flattened the
    # block to spaces. The span must still cover exactly that block, which is
    # why a block carries its own text rather than deriving it from the slice.
    wrapped = "Chapter One\n\nThe opening\nparagraph of\nthe book.\n"
    drafts = (
        BlockDraft(kind=BlockKind.HEADING, text="Chapter One", level=1),
        BlockDraft(
            kind=BlockKind.PARAGRAPH,
            text="The opening paragraph of the book.",
        ),
    )
    doc = build_from_drafts(source=wrapped, drafts=drafts)

    assert len(doc.blocks) == 2
    for block in doc.blocks:
        slice_ = wrapped[block.source_start : block.source_end]
        assert _same_ignoring_whitespace(slice_, block.text)

    # The wrapped paragraph is the case that matters: its slice carries the
    # newlines, its text does not, and the span is still exact.
    paragraph = doc.blocks[1]
    slice_ = wrapped[paragraph.source_start : paragraph.source_end]
    assert slice_ == "The opening\nparagraph of\nthe book."
    assert slice_ != paragraph.text


def test_contents_offsets_point_at_their_headings() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=DRAFTS)

    for entry in doc.toc:
        offset = int(entry.target_source_offset or 0)
        assert SOURCE[offset:].startswith(entry.title)


def test_a_well_covered_source_scores_high_confidence() -> None:
    doc = build_from_drafts(source=SOURCE, drafts=DRAFTS)

    assert doc.displayed_ratio > 0.75


def test_unlocatable_drafts_lower_confidence_rather_than_corrupting_spans() -> None:
    drafts = DRAFTS + (
        BlockDraft(kind=BlockKind.PARAGRAPH, text="Text that is not in the source."),
    )
    doc = build_from_drafts(source=SOURCE, drafts=drafts)

    # The bogus draft is dropped, and the real ones keep exact spans.
    assert len(doc.blocks) == len(DRAFTS)
    for block in doc.blocks:
        assert SOURCE[block.source_start : block.source_end] == block.text
