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

# An initialism the AUTHOR marked as one, by writing the stops: "U.K." Nothing
# else is expanded.
#
# A plain run of capitals used to be expanded too, on the reading that "CTO"
# wants spelling out. It cannot be told apart from an emphasised word; in a
# novel almost every run of capitals is emphasis. Measured on 2026-09-20 over
# `When the Wind Blows`: the rule fired 504 times across 235 distinct tokens,
# of which roughly 73 were initialisms (FBI, TV, MIT, NYU, DNA, EMS) and the
# rest were shouted prose, so a reader heard "P L E A S E help me" and
# "F I R S T F L I G H T". No shape separates FBI from KIT: not length, not
# vowels, not case. The length window made it incoherent within one sentence as
# well, since SOMEBODY at eight letters fell outside it while PLEASE at six
# fell inside.
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
            if (
                stripped
                and _SEPARATOR_ONLY.fullmatch(stripped)
                and not any(ch.isalnum() for ch in stripped)
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
        """Expand only what the author wrote as an initialism: "U.K." -> "U K"."""

        def undot(m: re.Match[str]) -> str:
            letters = [ch for ch in m.group(0) if ch.isalpha()]
            return " ".join(letters)

        return _DOTTED_INITIALISM.sub(undot, text)
