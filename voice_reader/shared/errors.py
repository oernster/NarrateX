"""Shared exception types.

These are intentionally framework-agnostic to keep clean boundaries.
"""

from __future__ import annotations


class VoiceReaderError(Exception):
    """Base error for the application."""


class BookConversionError(VoiceReaderError):
    """Raised when an input book cannot be converted to a supported format."""


class BookParseError(VoiceReaderError):
    """Raised when a book cannot be parsed."""


class BookHasNoTextError(VoiceReaderError):
    """Raised when a book opens cleanly and holds no text to read aloud.

    Not a parse failure: the file was read without complaint and simply had no
    words in it. Measured on 2026-09-21, six New Scientist issues printed to PDF
    carry every page as one picture with no text layer at all, so they parse to
    nothing. Loading one used to leave an empty reader and say nothing.
    """

    #: Addressed to the reader, since it is shown as it stands. It says what
    #: was found and the likeliest reason, without claiming the reason as fact:
    #: an EPUB of scanned pages and a blank text file arrive here too.
    READER_TEXT = (
        "This book holds no text to read aloud. Its pages are probably pictures "
        "of text, which NarrateX cannot read."
    )

    def __init__(self) -> None:
        super().__init__(self.READER_TEXT)


class BookIsProtectedError(BookHasNoTextError):
    """An EPUB that yielded no text because its pages are encrypted (DRM).

    A no-text book like any other, so every path that handles the one handles
    this; only the reason differs, because "probably pictures of text" sends
    the reader looking for the wrong fix.
    """

    READER_TEXT = (
        "This book is copy protected (DRM). NarrateX cannot read a protected "
        "book's text; a copy without protection opens normally."
    )


class CacheError(VoiceReaderError):
    """Raised for cache repository issues."""


class TTSError(VoiceReaderError):
    """Raised when the TTS engine fails."""


class PlaybackError(VoiceReaderError):
    """Raised for audio playback/streaming failures."""
