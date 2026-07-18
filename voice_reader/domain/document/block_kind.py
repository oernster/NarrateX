"""Domain: block kinds and their display/narration policy.

A block kind answers two independent questions:

- should this block appear in the reading pane
- should this block be spoken by the narrator

The answers are genuinely independent. A heading is both displayed and spoken,
a table-of-contents entry is neither (it is navigation, surfaced as a TOC rather
than as body text), and a code block is displayed but not spoken.

Keeping the policy here, rather than in the renderer and the narrator
separately, means the two consumers cannot drift apart.
"""

from __future__ import annotations

from enum import Enum


class BlockKind(Enum):
    """The kind of a single block of a document."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    BLOCK_QUOTE = "block_quote"
    CODE = "code"
    TOC_ENTRY = "toc_entry"
    PAGE_NUMBER = "page_number"
    RUNNING_HEAD = "running_head"
    SEPARATOR = "separator"

    @property
    def is_displayed(self) -> bool:
        """Whether the reading pane should render this block as body text."""

        return self in _DISPLAYED_KINDS

    @property
    def is_spoken(self) -> bool:
        """Whether the narrator should speak this block."""

        return self in _SPOKEN_KINDS


# Body content: what a reader expects to see in the pane.
_DISPLAYED_KINDS: frozenset[BlockKind] = frozenset(
    {
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.LIST_ITEM,
        BlockKind.BLOCK_QUOTE,
        BlockKind.CODE,
    }
)

# Spoken content: displayed body minus the kinds that narrate badly.
# Code is shown but not read aloud; punctuation and symbols make poor speech.
_SPOKEN_KINDS: frozenset[BlockKind] = frozenset(
    {
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.LIST_ITEM,
        BlockKind.BLOCK_QUOTE,
    }
)
