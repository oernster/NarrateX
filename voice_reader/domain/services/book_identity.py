"""The book id: what bookmarks, the resume position and shelf progress key on.

The id is a digest of the book's whole normalised text and nothing else. A
file renamed or moved keeps its id; two different books never share one merely
because they share a filename and an opening; an edit anywhere in the text
gives a new id, so a resume offset measured in the old text is never applied
to the new one.

Earlier versions digested the filename's stem plus the first 2000
characters. `legacy_book_id` reproduces that answer exactly, because it is the
only way to find the records an existing reader already has: a book opened
under the new id carries its legacy record over once (see
`BookmarkService.settle_book_records`).
"""

from __future__ import annotations

import hashlib

# Hex characters kept from the digest. Shared by both schemes so an old and a
# new id are the same shape on disk.
BOOK_ID_HEX_CHARS = 16

# How much of the text the legacy scheme digested after the stem.
_LEGACY_TEXT_PREFIX_CHARS = 2000


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[
        :BOOK_ID_HEX_CHARS
    ]


def book_id_for(normalized_text: str) -> str:
    """The id of a book whose normalised text is this."""

    return _digest(normalized_text)


def legacy_book_id(stem: str, normalized_text: str) -> str:
    """The id earlier versions gave the same file."""

    return _digest(stem + normalized_text[:_LEGACY_TEXT_PREFIX_CHARS])
