"""Domain service to detect a sensible narration start point.

Goal: skip boring front-matter (title pages, copyright, ToC) and start at the
first real content section (Chapter 1, Prologue, etc.).

This logic is heuristic by nature and intentionally pure (no IO) to keep it
unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReadingStart:
    start_char: int
    reason: str


@dataclass(frozen=True, slots=True)
class ReadingStartService:
    """Detect the character offset to begin narration."""

    max_scan_chars: int = 60_000
    max_prose_seek_chars: int = 30_000

    def detect_start(self, text: str) -> ReadingStart:
        normalized = text
        scan = normalized[: self.max_scan_chars]

        candidates: list[ReadingStart] = []

        # 0) Introduction is preferred over Chapter 1 / Prologue when present.
        for m in re.finditer(r"(?im)^\s*introduction\s*$", scan):
            line = self._line_at(scan, m.start())
            if self._looks_like_toc_entry(line):
                continue
            candidates.append(
                ReadingStart(
                    start_char=self._start_after_heading(scan, m.end()),
                    reason="Detected Introduction",
                )
            )
            break

        # 1) Explicit Chapter 1 markers.
        for pat in self._chapter_one_patterns():
            for m in pat.finditer(scan):
                line = self._line_at(scan, m.start())
                if self._looks_like_toc_entry(line):
                    continue
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, m.end()),
                        reason="Detected Chapter 1",
                    )
                )
                break

        # 2) Prologue markers.
        for pat in self._prologue_patterns():
            for m in pat.finditer(scan):
                line = self._line_at(scan, m.start())
                if self._looks_like_toc_entry(line):
                    continue
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, m.end()),
                        reason="Detected Prologue",
                    )
                )
                break

        # 3) Numeric heading ("1.", "1 ") on a line by itself.
        m = re.search(r"(?im)^(\s*1\s*(?:\.|\))\s*)$", scan)
        if m:
            candidates.append(
                ReadingStart(
                    start_char=self._start_after_heading(scan, m.end()),
                    reason="Detected numeric heading 1",
                )
            )

        # 4) Fallback: after Table of Contents section if present.
        toc_end = self._detect_toc_end(scan)
        if toc_end is not None:
            candidates.append(
                ReadingStart(
                    start_char=toc_end,
                    reason="Skipped Table of Contents",
                )
            )

        # Choose earliest plausible start that is not too early.
        best = self._pick_best(candidates)
        if best is None:
            return ReadingStart(start_char=0, reason="Start at beginning")

        start = self._skip_leading_whitespace(normalized, best.start_char)
        start = self._advance_to_prose(normalized, start)
        return ReadingStart(start_char=start, reason=best.reason)

    def _advance_to_prose(self, text: str, start: int) -> int:
        """Skip outline-like headings until we hit real prose.

        Many real EPUBs contain an index / outline with headings and numbering
        like "1.1", "1.1.2" followed by short section titles. This is useful
        visually but terrible when spoken.

        We seek forward up to `max_prose_seek_chars` for a line that looks like
        a paragraph (punctuation and/or sufficient word count).
        """

        end = min(len(text), start + self.max_prose_seek_chars)
        window = text[start:end]

        offset = start
        for line in window.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped:
                offset += len(line)
                continue

            if self._looks_like_toc_entry(stripped) or self._looks_like_outline_line(
                stripped
            ):
                offset += len(line)
                continue

            if self._looks_like_prose(stripped):
                return self._skip_leading_whitespace(text, offset)

            # Otherwise treat as a heading and keep scanning.
            offset += len(line)

        return start

    @staticmethod
    def _looks_like_outline_line(line: str) -> bool:
        # Number-only ("1", "1.1.2")
        if re.match(r"^\d+(?:\.\d+)*$", line):
            return True
        # "1.1 Title" or "1 Title"
        if re.match(r"^\d+(?:\.\d+)*\s+\S+", line):
            return True
        # Short standalone headings (no punctuation)
        if len(line) <= 40 and not re.search(r"[.!?]", line):
            return True
        return False

    @staticmethod
    def _looks_like_prose(line: str) -> bool:
        words = [w for w in re.split(r"\s+", line) if w]
        # Short headings sometimes end with a period. Require enough words/length.
        if re.search(r"[.!?]", line):
            if len(words) >= 12 or len(line) >= 90:
                return True
            return False

        # Or a sufficiently long line with multiple words.
        if len(words) >= 14 and len(line) >= 80:
            return True
        return False

    @staticmethod
    def _skip_leading_whitespace(text: str, idx: int) -> int:
        i = max(0, min(idx, len(text)))
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    @staticmethod
    def _pick_best(candidates: list[ReadingStart]) -> ReadingStart | None:
        if not candidates:
            return None
        intro = [c for c in candidates if "Introduction" in c.reason]
        if intro:
            return min(intro, key=lambda c: c.start_char)
        # Prefer Chapter 1 over others if multiple exist.
        chapter1 = [c for c in candidates if "Chapter 1" in c.reason]
        if chapter1:
            return min(chapter1, key=lambda c: c.start_char)
        prologue = [c for c in candidates if "Prologue" in c.reason]
        if prologue:
            return min(prologue, key=lambda c: c.start_char)
        numeric = [c for c in candidates if "numeric heading" in c.reason]
        if numeric:
            return min(numeric, key=lambda c: c.start_char)
        return min(candidates, key=lambda c: c.start_char)

    @staticmethod
    def _detect_toc_end(scan: str) -> int | None:
        # Heuristic:
        # - find a "Contents" / "Table of Contents" heading near the beginning
        # - then skip subsequent lines that look like TOC entries
        toc_heading = re.search(r"(?im)^(\s*(table of contents|contents)\s*)$", scan)
        if not toc_heading:
            return None
        start = toc_heading.end()

        # Consume likely TOC lines.
        lines = scan[start:].splitlines(keepends=True)
        offset = start
        consumed_any = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                offset += len(line)
                continue
            if ReadingStartService._looks_like_toc_entry(stripped):
                consumed_any = True
                offset += len(line)
                continue
            # Stop at first non-TOC-looking line, after consuming some entries.
            if consumed_any:
                break
            # If the line after heading doesn't look like TOC, don't skip.
            return None
        return offset if consumed_any else None

    @staticmethod
    def _looks_like_toc_entry(line: str) -> bool:
        # Typical TOC lines:
        # "Chapter 1  ....  12", "1. Something  7", "Prologue  i"
        if re.search(r"(?i)\bchapter\b\s+\d+", line):
            # Only treat as TOC if there's a page reference / leader dots.
            if re.search(r"\.{2,}\s*(\d+|[ivxlcdm]+)\s*$", line, re.I):
                return True
            if re.search(r"\s+(\d+|[ivxlcdm]+)\s*$", line, re.I) and len(line) > 12:
                return True
        if re.match(r"^\s*\d+\s*[.)]\s+.+\s+\d+\s*$", line):
            return True
        if re.match(r"^\s*(prologue|epilogue|introduction)\b.*\s+\d+\s*$", line, re.I):
            return True
        if re.search(r"\.{2,}\s*\d+\s*$", line):
            return True
        # Roman numeral page refs.
        if re.match(r"^\s*.+\s+([ivxlcdm]+)\s*$", line, re.I):
            return True
        return False

    @staticmethod
    def _line_at(text: str, idx: int) -> str:
        """Return the full line containing idx."""

        if idx < 0:
            idx = 0
        if idx > len(text):
            idx = len(text)
        line_start = text.rfind("\n", 0, idx)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        line_end = text.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        return text[line_start:line_end].strip()

    @staticmethod
    def _start_after_heading(text: str, heading_end: int) -> int:
        """Return an index just after the heading line.

        This prevents the narrator from reading section titles like
        "INTRODUCTION" or "CHAPTER 1" aloud.
        """

        if heading_end < 0:
            heading_end = 0
        if heading_end > len(text):
            heading_end = len(text)

        # Find the end of the heading line starting from the end of the match.
        line_end = text.find("\n", heading_end)
        if line_end == -1:
            return len(text)
        # Advance past the newline.
        i = line_end + 1
        # Skip blank lines and indentation.
        while i < len(text) and text[i].isspace():
            i += 1

        # If the next line still looks like a standalone heading (all-caps short
        # subtitle), skip it once.
        next_line = ReadingStartService._line_at(text, i)
        if ReadingStartService._looks_like_standalone_title(next_line):
            next_line_end = text.find("\n", i)
            if next_line_end != -1:
                i = next_line_end + 1
                while i < len(text) and text[i].isspace():
                    i += 1
        return i

    @staticmethod
    def _looks_like_standalone_title(line: str) -> bool:
        if not line:
            return False
        # Avoid skipping real sentences.
        if any(ch in line for ch in (".", "!", "?")):
            return False
        # Short lines in uppercase are often section titles/subtitles.
        letters = [c for c in line if c.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for c in letters if c.isupper()) / float(len(letters))
        return upper_ratio > 0.9 and len(line) <= 60

    @staticmethod
    def _chapter_one_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*chapter\s+1\b", re.IGNORECASE),
            re.compile(r"(?im)^\s*chapter\s+i\b", re.IGNORECASE),
            re.compile(r"(?im)^\s*ch\.\s*1\b", re.IGNORECASE),
        ]

    @staticmethod
    def _prologue_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*prologue\b", re.IGNORECASE),
            re.compile(r"(?im)^\s*introduction\b", re.IGNORECASE),
        ]
