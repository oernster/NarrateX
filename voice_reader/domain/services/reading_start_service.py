"""Domain service to detect a sensible narration start point."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReadingStart:
    start_char: int
    reason: str


@dataclass(frozen=True, slots=True)
class ReadingStartService:
    """Detect the character offset to begin narration.

    Hard requirement:
    - skip Table of Contents if present
    - jump to the first real structural section (Introduction / Foreword /
      Preface / Acknowledgements / Prologue / Chapter 1)
    - start reading at the FIRST sentence under that heading
    """

    max_scan_chars: int = 60_000
    max_prose_seek_chars: int = 40_000

    def detect_start(self, text: str) -> ReadingStart:
        scan = text[: self.max_scan_chars]

        # 1) Skip ToC first, deterministically.
        toc_end = self._detect_toc_end(scan)
        search_start = toc_end if toc_end is not None else 0
        search = scan[search_start:]

        # 2) Find the earliest real section AFTER the ToC.
        candidates: list[ReadingStart] = []

        def add_first_match(patterns: list[re.Pattern[str]], reason: str) -> None:
            earliest: int | None = None
            earliest_end: int | None = None

            for pat in patterns:
                m = pat.search(search)
                if not m:
                    continue
                if earliest is None or m.start() < earliest:
                    earliest = m.start()
                    earliest_end = m.end()

            if earliest is not None and earliest_end is not None:
                absolute_end = search_start + earliest_end
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, absolute_end),
                        reason=reason,
                    )
                )

        # Priority is resolved later; here we just gather the first match of each type.
        add_first_match(self._introduction_patterns(), "Detected Introduction")
        add_first_match(self._frontmatter_patterns(), "Detected Frontmatter")
        add_first_match(self._prologue_patterns(), "Detected Prologue")
        add_first_match(self._chapter_one_patterns(), "Detected Chapter 1")

        # 3) Fallback: if no structural heading found after ToC, start after ToC.
        if not candidates:
            if toc_end is not None:
                candidates.append(
                    ReadingStart(
                        start_char=toc_end,
                        reason="Skipped Table of Contents",
                    )
                )
            else:
                return ReadingStart(start_char=0, reason="Start at beginning")

        best = self._pick_best(candidates)

        start = self._skip_leading_whitespace(text, best.start_char)
        start = self._seek_first_paragraph(text, start)

        return ReadingStart(start_char=start, reason=best.reason)

    def _seek_first_paragraph(self, text: str, start: int) -> int:
        """Find the first real prose paragraph after a structural heading."""

        end = min(len(text), start + self.max_prose_seek_chars)
        window = text[start:end]

        offset = start

        for line in window.splitlines(keepends=True):
            stripped = line.strip()

            if not stripped:
                offset += len(line)
                continue

            # Skip obvious structural junk
            if self._looks_like_toc_entry(stripped):
                offset += len(line)
                continue

            if self._looks_like_outline_line(stripped):
                offset += len(line)
                continue

            if self._looks_like_backmatter(stripped):
                return start

            # FIRST real sentence/paragraph wins
            if self._looks_like_paragraph(stripped):
                return self._skip_leading_whitespace(text, offset)

            offset += len(line)

        return start

    @staticmethod
    def _looks_like_paragraph(line: str) -> bool:
        """Accept actual prose, including short first sentences."""

        words = [w for w in re.split(r"\s+", line) if w]

        if len(words) < 3:
            return False

        if not any(ch.islower() for ch in line):
            return False

        # A normal sentence should be accepted immediately.
        if re.search(r"[.!?]\s*$", line):
            return True

        # Otherwise accept clearly paragraph-like long lines.
        if len(words) >= 14 or len(line) >= 90:
            return True

        return False

    @staticmethod
    def _looks_like_outline_line(line: str) -> bool:
        """Reject numbering and short heading lines."""

        # Number-only like "4.2.2"
        if re.match(r"^\d+(?:\.\d+)*$", line):
            return True

        # Numbered heading like "4.2 Chapter title"
        if re.match(r"^\d+(?:\.\d+)*\s+\S+", line):
            return True

        # Very short non-sentence headings
        if len(line.split()) <= 4 and not re.search(r"[.!?]\s*$", line):
            return True

        return False

    @staticmethod
    def _looks_like_toc_entry(line: str) -> bool:
        """Reject typical Table of Contents lines."""

        # Dotted leader + page number
        if re.search(r"\.{2,}\s*(\d+|[ivxlcdm]+)\s*$", line, re.I):
            return True

        # Trailing page number / roman numeral, e.g. "Prologue i"
        if re.match(r"^.+\s+(\d+|[ivxlcdm]+)\s*$", line, re.I):
            # Be conservative: TOC entries are usually fairly short.
            if len(line) <= 120:
                return True

        return False

    @staticmethod
    def _looks_like_backmatter(line: str) -> bool:
        return bool(
            re.match(
                r"(?im)^\s*(appendix|afterword|epilogue|bibliography|references|index)\b",
                line,
            )
        )

    @staticmethod
    def _skip_leading_whitespace(text: str, idx: int) -> int:
        while idx < len(text) and text[idx].isspace():
            idx += 1
        return idx

    @staticmethod
    def _pick_best(candidates: list[ReadingStart]) -> ReadingStart | None:
        """
        Choose the earliest structural heading in the document.

        This guarantees we land on Prologue when it precedes Introduction,
        which is the normal book structure.
        """
        if not candidates:
            return None

        return min(candidates, key=lambda c: c.start_char)

    @staticmethod
    def _start_after_heading(text: str, heading_match_end: int) -> int:
        """Move to the first non-whitespace character after the heading line."""

        line_end = text.find("\n", heading_match_end)
        if line_end == -1:
            return len(text)

        i = line_end + 1
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    @staticmethod
    def _detect_toc_end(scan: str) -> int | None:
        """Detect the end of a real Table of Contents block."""

        toc_heading = re.search(r"(?im)^\s*(table of contents|contents)\s*$", scan)
        if not toc_heading:
            return None

        start = toc_heading.end()
        lines = scan[start:].splitlines(keepends=True)

        offset = start
        consumed_any = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                offset += len(line)
                continue

            if (
                ReadingStartService._looks_like_toc_entry(stripped)
                or ReadingStartService._looks_like_outline_line(stripped)
            ):
                consumed_any = True
                offset += len(line)
                continue

            # First non-ToC-looking line after consuming entries ends the ToC.
            if consumed_any:
                break

            # If the line after "Contents" doesn't look like ToC, abort.
            return None

        return offset if consumed_any else None

    @staticmethod
    def _introduction_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*introduction\s*$"),
        ]

    @staticmethod
    def _frontmatter_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*foreword\s*$"),
            re.compile(r"(?im)^\s*preface\s*$"),
            re.compile(r"(?im)^\s*acknowledgements?\s*$"),
            re.compile(r"(?im)^\s*acknowledgments\s*$"),
        ]

    @staticmethod
    def _prologue_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*prologue\s*$"),
        ]

    @staticmethod
    def _chapter_one_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*chapter\s+1\b"),
            re.compile(r"(?im)^\s*chapter\s+i\b"),
            re.compile(r"(?im)^\s*ch\.\s*1\b"),
        ]