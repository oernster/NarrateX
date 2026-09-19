"""The book formats NarrateX opens: one declaration, read by everything.

FR-BS-002a and FR-BS-002b. The file dialog's filter, the shelf scanner, the
converter and the cover reader all need the same answer to "is this a book?".
Two lists drift; the one that drifts silently is the scanner's, because a book
that opens through the dialog yet never appears on the shelf looks like a
missing book rather than a missing extension.

Ordering matters in `PREFERENCE`: a work present in several formats is opened
in the one that costs least to read. Measured on 2026-09-19, a Kindle format
costs a 2.3 second Calibre conversion that an EPUB does not.
"""

from __future__ import annotations

# Formats read without a conversion step.
NATIVE: tuple[str, ...] = (".epub", ".pdf", ".txt", ".md", ".markdown")

# Formats reaching the reader through a Calibre conversion.
KINDLE: tuple[str, ...] = (".mobi", ".azw", ".azw3", ".prc", ".kfx")

# Every extension the application recognises as a book.
RECOGNISED: frozenset[str] = frozenset(NATIVE + KINDLE)

# Cheapest first. FR-BS-013 opens the earliest format a work holds.
PREFERENCE: tuple[str, ...] = (
    ".epub",
    ".pdf",
    ".txt",
    ".md",
    ".markdown",
    ".azw3",
    ".mobi",
    ".azw",
    ".prc",
    ".kfx",
)

# Kindle formats built on the PalmDB container, whose metadata and cover can be
# read directly from an EXTH header with no conversion. `.kfx` is a different
# container entirely and is deliberately absent.
PALM_CONTAINER: frozenset[str] = frozenset({".mobi", ".azw", ".azw3", ".prc"})


def is_book(suffix: str) -> bool:
    """True when this file extension is one NarrateX opens."""

    return suffix.lower() in RECOGNISED


def needs_conversion(suffix: str) -> bool:
    """True when reading this format costs a Calibre conversion."""

    return suffix.lower() in KINDLE


def reads_palm_container(suffix: str) -> bool:
    """True when metadata and cover can be read straight from the file."""

    return suffix.lower() in PALM_CONTAINER


def preference_rank(suffix: str) -> int:
    """Position in `PREFERENCE`; unrecognised formats sort last."""

    lowered = suffix.lower()
    if lowered in PREFERENCE:
        return PREFERENCE.index(lowered)
    return len(PREFERENCE)


def dialog_filter() -> str:
    """The Qt file-dialog filter string, derived rather than written twice."""

    patterns = " ".join("*" + suffix for suffix in PREFERENCE)
    return f"Books ({patterns});;All Files (*)"
