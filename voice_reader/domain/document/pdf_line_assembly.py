"""Assemble classified PDF lines back into whole blocks of text.

Classification (`pdf_lines`) decides what each extracted line is. This module
owns the other half of the job: joining wrapped lines into one paragraph or
heading, healing words the typesetting split across line ends, and rejoining a
heading whose section number was set on its own line.

This module is pure and text-only, so every rule here is testable without
opening a PDF.
"""

from __future__ import annotations

import re

from voice_reader.domain.document.anchoring import BlockDraft
from voice_reader.domain.document.block_kind import BlockKind

# A word broken across a line end: "deci-" followed by "sion". A lowercase
# continuation means a split word; an uppercase one means a real hyphenated
# compound at a line end, which is left alone.
#
# Both hyphens count. A typeset PDF breaks words on a non-breaking hyphen as
# readily as on a plain one, and the extraction folds the two together before
# healing them, so matching only the plain one leaves every paragraph broken on
# the other kind unanchorable.
_LINE_BREAK_HYPHEN = re.compile(r"([A-Za-z])[-‑]$")
_LOWERCASE_START = re.compile(r"^[a-z]")

# A heading that is nothing but its own section number: "8", "8.1", "3.1.1".
# These are set on their own line often enough that they need rejoining with
# the title that follows.
_SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?$")


def join_paragraph_lines(parts: tuple[str, ...]) -> str:
    """Join wrapped lines into one paragraph, healing split words.

    Mirrors the dehyphenation the text extraction already applies, so the
    resulting text matches the canonical text and can be anchored to it.
    """

    joined = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if not joined:
            joined = piece
            continue
        if _LINE_BREAK_HYPHEN.search(joined) and _LOWERCASE_START.match(piece):
            joined = joined[:-1] + piece
            continue
        joined = f"{joined} {piece}"
    return joined


def rejoin_split_numbering(drafts: tuple[BlockDraft, ...]) -> tuple[BlockDraft, ...]:
    """Rejoin a heading whose number was typeset on its own line.

    Typesetting often sets "8.1" and "From possibility to constraint" as
    separate lines, so they arrive as two headings. Left apart, the number
    becomes a navigation entry of its own that says nothing, and the title
    loses the number that identifies it.

    Rejoining is safe against the canonical text because matching ignores
    whitespace: "8.1 From possibility to constraint" and the source's
    "8.1\\nFrom possibility to constraint" reduce to the same thing.
    """

    rejoined: list[BlockDraft] = []
    pending: BlockDraft | None = None

    for draft in drafts:
        is_heading = draft.kind is BlockKind.HEADING

        if is_heading and _SECTION_NUMBER.match(draft.text):
            # Two numbers in a row means the first had no title to join.
            if pending is not None:
                rejoined.append(pending)
            pending = draft
            continue

        if pending is not None:
            if is_heading:
                rejoined.append(
                    BlockDraft(
                        kind=BlockKind.HEADING,
                        text=f"{pending.text} {draft.text}",
                        level=min(pending.level, draft.level),
                    )
                )
                pending = None
                continue
            rejoined.append(pending)
            pending = None

        rejoined.append(draft)

    if pending is not None:
        rejoined.append(pending)

    return tuple(rejoined)
