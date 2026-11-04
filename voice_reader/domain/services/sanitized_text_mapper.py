"""Domain service: sanitize text for TTS while producing a char mapping.

Goal:
- We send sanitized text to the TTS engine for better spoken output.
- UI highlighting must map back to the *original* reader text.

This service produces:
- speak_text: sanitized text for TTS
- speak_to_original: list[int] mapping each character index in speak_text to a
  best-effort absolute character offset in the original (unsanitized) chunk text.

The mapping is an alignment of the two texts, not a scan. A scan that sought
each spoken character further along the original was measured on 2026-11-04
against a sentence holding a formula: the words said for the symbols ("the
sum from k equals 0 to m of") have no counterpart in the original, so the
scan ran ahead looking for them and every later word of the chunk mapped to
its last character. Matching blocks between the two texts place what matches
exactly; what the sanitizer added stays on the character it was said for.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer

_UNMAPPED = -1


@dataclass(frozen=True, slots=True)
class SanitizedTextMapping:
    speak_text: str
    # For each index i in speak_text, speak_to_original[i] is an index into the
    # original chunk text. Indices are chunk-local (0..len(chunk_text)).
    speak_to_original: list[int]


def _folded(text: str) -> list[str]:
    """One entry per character, so an index into it is an index into `text`."""

    return [char.casefold() for char in text]


@dataclass(frozen=True, slots=True)
class SanitizedTextMapper:
    sanitizer: SpokenTextSanitizer = SpokenTextSanitizer()

    def sanitize_with_mapping(self, *, original_text: str) -> SanitizedTextMapping:
        """Return sanitized speak_text plus a per-character index mapping.

        Matching is case-insensitive, so an initialism the sanitizer spelled
        out still lands on its letters. A spoken character the original does
        not hold maps to the last original character matched before it, so
        the highlight waits on the symbol being said; before any match it
        maps to the first match, else to the start when nothing matches.
        """

        speak = self.sanitizer.sanitize(original_text)
        if not speak:
            return SanitizedTextMapping(speak_text="", speak_to_original=[])

        mapping = [_UNMAPPED] * len(speak)
        matcher = SequenceMatcher(
            None, _folded(original_text), _folded(speak), autojunk=False
        )
        for original_at, speak_at, length in matcher.get_matching_blocks():
            for offset in range(length):
                mapping[speak_at + offset] = original_at + offset

        first = next((at for at in mapping if at != _UNMAPPED), 0)
        last = first
        for index, at in enumerate(mapping):
            if at == _UNMAPPED:
                mapping[index] = last
            else:
                last = at

        return SanitizedTextMapping(speak_text=speak, speak_to_original=mapping)
