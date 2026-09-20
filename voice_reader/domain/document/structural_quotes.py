"""A blockquote that is most of a book is not a quotation.

Some Kindle books indent their body text with `<blockquote>`; a conversion to
EPUB carries the tag across unchanged. NarrateX then renders the whole book
italic, indented and spaced as though every paragraph were quoted matter.

**Measured, not assumed.** Over the ten EPUBs in the reference library on
2026-09-20, blockquotes numbered between 0 and 20 against thousands of
paragraphs, never as much as 1% of a book. A Kindle conversion of `When the
Wind Blows` came out at 3450 blockquotes against 126 paragraphs: 93% of it.

The separation is wide enough that no proportion needs picking. A comparison
does it: where quoted blocks outnumber plain ones, the tag is being used for
indentation and every block wearing it is an ordinary paragraph. The worst real
book in the library sits at 20 against 3516, so nothing in it comes close.
"""

from __future__ import annotations

from collections.abc import Sequence

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind


def quotes_are_structural(drafts: Sequence[BlockDraft]) -> bool:
    """Whether this book's blockquotes are indentation rather than quotation."""

    quoted = sum(1 for d in drafts if d.kind is BlockKind.BLOCK_QUOTE)
    plain = sum(1 for d in drafts if d.kind is BlockKind.PARAGRAPH)
    return quoted > plain


def as_ordinary_paragraphs(drafts: Sequence[BlockDraft]) -> list[BlockDraft]:
    """The drafts, with a book-wide blockquote read as the prose it is.

    A book whose quotes are genuine quotes is handed back untouched, so a
    novel that quotes a letter still shows the letter as a quotation.
    """

    if not quotes_are_structural(drafts):
        return list(drafts)
    return [
        (
            BlockDraft(kind=BlockKind.PARAGRAPH, text=d.text, level=d.level)
            if d.kind is BlockKind.BLOCK_QUOTE
            else d
        )
        for d in drafts
    ]
