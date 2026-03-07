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


class CacheError(VoiceReaderError):
    """Raised for cache repository issues."""


class TTSError(VoiceReaderError):
    """Raised when the TTS engine fails."""


class PlaybackError(VoiceReaderError):
    """Raised for audio playback/streaming failures."""
