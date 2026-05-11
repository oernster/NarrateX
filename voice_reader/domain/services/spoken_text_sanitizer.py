"""Domain service to sanitize text before sending to TTS.

Purpose: remove structural numbering ("1", "1.1.2") and numbering prefixes so the
listener doesn't hear outline junk while keeping UI highlighting based on the
original text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_ONLY = re.compile(r"^\s*\d+(?:\.\d+)*\s*$")
_NUMBER_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\s+")

# Initialisms/acronyms like "CTO", "API", "UK".
# - include plural 's' ("APIs")
# - handle hyphenated contexts ("CTO-level") via non-alpha boundaries
_ACRONYM_TOKEN = re.compile(r"(?<![A-Za-z])([A-Z]{2,6})(s)?(?![A-Za-z])")
_DOTTED_INITIALISM = re.compile(r"\b(?:[A-Z]\.)(?:[A-Z]\.)(?:[A-Z]\.){0,4}")
_MULTI_DOT = re.compile(r"\.{2,}")
_DOTLIKE = re.compile(r"[\u2024\u2219\u00B7\uFF0E\uFE52]")
_ISOLATED_DOT = re.compile(r"\s+\.\s+")

# Separator-only lines (common in plain-text books and PDF/EPUB extracts).
#
# Root-cause fix motivation:
# A separator-only chunk like "---" can be considered "speakable" by our current
# sanitization (it's non-empty) but may yield *no audio* from some TTS engines.
# That synthesis failure can bubble up and look like playback restarting.
#
# We treat these as non-content structure and drop them at sanitization time.
_SEPARATOR_ONLY = re.compile(r"^[\s\-\u2013\u2014\u2212_\*=~]+$")


@dataclass(frozen=True, slots=True)
class SpokenTextSanitizer:
    def sanitize(self, text: str) -> str:
        # Operate line-by-line to preserve some structure while dropping
        # outline numbering.
        lines: list[str] = []
        for raw in text.splitlines():
            # Drop separator-only structure lines (e.g. "---", "--", "____").
            # This is semantic (no words), not based on a specific dash count.
            stripped = str(raw or "").strip()
            if stripped and _SEPARATOR_ONLY.fullmatch(stripped) and not any(
                ch.isalnum() for ch in stripped
            ):
                continue

            if _NUMBER_ONLY.match(raw):
                continue
            cleaned = _NUMBER_PREFIX.sub("", raw)
            cleaned = cleaned.strip()
            if cleaned:
                lines.append(cleaned)

        # IMPORTANT: use spaces instead of newlines.
        # Many TTS engines interpret newlines as stronger breaks and can add
        # unnatural pauses.
        out = " ".join(lines).strip()
        out = self._normalize_punctuation(out)
        out = self._expand_initialisms(out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    @staticmethod
    def _normalize_punctuation(text: str) -> str:
        # Reduce odd cadence from double-dots / ellipses produced by OCR/EPUB
        # extraction.
        text = text.replace("…", "...")
        # Normalise other dot-like characters (common in PDFs / OCR).
        text = _DOTLIKE.sub(".", text)
        # Collapse multi-dot sequences.
        text = _MULTI_DOT.sub(".", text)
        # Remove isolated dots left behind by broken ellipses (". ." -> " ").
        # Keep sentence-ending punctuation at the end of the string.
        text = _ISOLATED_DOT.sub(" ", text)
        return text

    @staticmethod
    def _expand_initialisms(text: str) -> str:
        # Expand dotted forms first: "U.K." -> "U K"
        def undot(m: re.Match[str]) -> str:
            token = m.group(0)
            letters = [ch for ch in token if ch.isalpha()]
            return " ".join(letters)

        text = _DOTTED_INITIALISM.sub(undot, text)

        # Expand plain tokens: "CTO" -> "C T O"; "APIs" -> "A P I s"
        def expand(m: re.Match[str]) -> str:
            letters = list(m.group(1))
            plural = m.group(2) or ""
            expanded = " ".join(letters)
            if plural:
                expanded = f"{expanded} {plural}"
            return expanded

        return _ACRONYM_TOKEN.sub(expand, text)
