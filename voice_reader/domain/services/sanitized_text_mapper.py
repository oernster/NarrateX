"""Domain service: sanitize text for TTS while producing a char mapping.

Goal:
- We send sanitized text to the TTS engine for better spoken output.
- UI highlighting must map back to the *original* reader text.

This service produces:
- speak_text: sanitized text for TTS
- speak_to_original: list[int] mapping each character index in speak_text to a
  best-effort absolute character offset in the original (unsanitized) chunk text.

The mapping is intentionally best-effort:
- If sanitization drops characters (e.g. outline numbering), the mapping will
  skip them.
- When sanitization normalizes punctuation or whitespace, mapping prefers the
  closest matching original character.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.services.spoken_text_sanitizer import SpokenTextSanitizer


@dataclass(frozen=True, slots=True)
class SanitizedTextMapping:
    speak_text: str
    # For each index i in speak_text, speak_to_original[i] is an index into the
    # original chunk text. Indices are chunk-local (0..len(chunk_text)).
    speak_to_original: list[int]


@dataclass(frozen=True, slots=True)
class SanitizedTextMapper:
    sanitizer: SpokenTextSanitizer = SpokenTextSanitizer()

    def sanitize_with_mapping(self, *, original_text: str) -> SanitizedTextMapping:
        """Return sanitized speak_text plus a per-character index mapping.

        Strategy:
        1. Sanitize with existing sanitizer (single source of truth for TTS).
        2. Build mapping by greedily aligning speak_text to original_text.

        The greedy alignment is resilient to dropped prefixes and whitespace
        normalization.
        """

        speak = self.sanitizer.sanitize(original_text)
        if not speak:
            return SanitizedTextMapping(speak_text="", speak_to_original=[])

        # Greedy scan. Prefer exact char match (case-sensitive), otherwise allow
        # whitespace collapsing and punctuation normalization.
        mapping: list[int] = []
        o = 0
        orig = original_text

        def _is_space(ch: str) -> bool:
            return ch.isspace()

        for i, ch in enumerate(speak):
            # For spaces, map to the next whitespace run (or previous char).
            if _is_space(ch):
                while o < len(orig) and not _is_space(orig[o]):
                    o += 1
                if o >= len(orig):
                    mapping.append(max(0, len(orig) - 1))
                    continue
                mapping.append(o)
                while o < len(orig) and _is_space(orig[o]):
                    o += 1
                continue

            # Seek the next matching character.
            found = -1
            for j in range(o, len(orig)):
                if orig[j] == ch:
                    found = j
                    break
            if found == -1:
                # Fallback: case-insensitive match.
                for j in range(o, len(orig)):
                    if orig[j].casefold() == ch.casefold():
                        found = j
                        break

            if found == -1:
                # Last resort: map to current scan pos (clamped).
                mapping.append(min(max(o, 0), max(0, len(orig) - 1)))
                continue

            mapping.append(found)
            o = found + 1

        return SanitizedTextMapping(speak_text=speak, speak_to_original=mapping)

