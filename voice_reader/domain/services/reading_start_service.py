"""Domain service to detect a sensible narration start point."""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.text_patterns import contains_dotted_leader

from voice_reader.domain.services import reading_start_toc


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

    # PDFs can contain extremely long Tables of Contents (including subsection
    # listings) where the first body chapter is far beyond 60k characters.
    # Keep this high enough to reliably reach the first real body heading.
    max_scan_chars: int = 250_000
    max_prose_seek_chars: int = 40_000

    def detect_start(self, text: str) -> ReadingStart:
        scan = text[: self.max_scan_chars]

        # 1) Skip ToC first, deterministically.
        toc_end = reading_start_toc.detect_toc_end(
            scan=scan,
            looks_like_structural_heading=self._looks_like_structural_heading,
        )
        search_start = toc_end if toc_end is not None else 0
        search = scan[search_start:]

        # 2) Find the earliest real section AFTER the ToC.
        candidates: list[ReadingStart] = []

        def add_first_match(patterns: list[re.Pattern[str]], reason: str) -> None:
            earliest_start: int | None = None
            earliest_end: int | None = None

            for pat in patterns:
                for m in pat.finditer(search):
                    abs_start = int(search_start) + int(m.start())
                    abs_end = int(search_start) + int(m.end())

                    if reading_start_toc.is_toc_wrapped_heading_match(
                        scan=scan,
                        absolute_match_start=int(abs_start),
                    ):
                        continue

                    if earliest_start is None or int(m.start()) < int(earliest_start):
                        earliest_start = int(m.start())
                        earliest_end = int(m.end())
                    # Since we're scanning left-to-right per-pattern, the first
                    # valid match is the earliest for that pattern.
                    break

            if earliest_start is not None and earliest_end is not None:
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
        assert best is not None

        start = self._skip_leading_whitespace(text, best.start_char)
        start = self._seek_first_paragraph(text, start)

        return ReadingStart(start_char=start, reason=best.reason)

    # ---- Backwards-compatible helpers for existing tests/callers ----
    @staticmethod
    def _detect_toc_end(scan: str) -> int | None:
        """Compatibility wrapper retained for older tests."""

        return reading_start_toc.detect_toc_end(
            scan=str(scan or ""),
            looks_like_structural_heading=ReadingStartService._looks_like_structural_heading,
        )

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

        # Accept very short first sentences like "Real content.".
        # Keep 1-word sentences rejected (e.g. "Short.") for existing edge-case tests.
        if len(words) >= 2 and re.search(r"[.!?]\s*$", line):
            return True

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

    # ---- Backwards-compatible helpers for existing tests/callers ----
    @staticmethod
    def _looks_like_prose(line: str) -> bool:
        """Legacy alias for prose detection.

        Tests and older call sites refer to `_looks_like_prose()`. The current
        implementation uses `_looks_like_paragraph()`.
        """

        return ReadingStartService._looks_like_paragraph(line)

    @staticmethod
    def _line_at(text: str, idx: int) -> str:
        """Return the line containing `idx` (clamped to the document bounds)."""

        if not text:
            return ""

        i = max(0, min(int(idx), len(text) - 1))

        line_start = text.rfind("\n", 0, i)
        line_start = 0 if line_start == -1 else line_start + 1

        line_end = text.find("\n", i)
        line_end = len(text) if line_end == -1 else line_end

        return text[line_start:line_end].strip("\r\n")

    @staticmethod
    def _looks_like_outline_line(line: str) -> bool:
        return reading_start_toc.looks_like_outline_line(line)

    @staticmethod
    def _looks_like_toc_entry(line: str) -> bool:
        return reading_start_toc.looks_like_toc_entry(line)

    @staticmethod
    def _looks_like_backmatter(line: str) -> bool:
        pat = r"(?im)^\s*(appendix|afterword|epilogue|bibliography|references|index)\b"
        return bool(re.match(pat, line))

    @staticmethod
    def _skip_leading_whitespace(text: str, idx: int) -> int:
        while idx < len(text) and text[idx].isspace():
            idx += 1
        return idx

    @staticmethod
    def _pick_best(candidates: list[ReadingStart]) -> ReadingStart | None:
        """
        Choose the earliest structural heading in the document.

        This matches typical book flow: if a Prologue appears before an
        Introduction, narration should start at the Prologue.
        """
        if not candidates:
            return None

        return min(candidates, key=lambda c: int(c.start_char))

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
    @staticmethod
    def _looks_like_structural_heading(line: str) -> bool:
        """Detect *clean* headings that indicate we're out of the ToC.

        This must not match typical ToC entry lines like:
        - "Chapter 1 .... 1"
        - "Introduction .... v"

        It should match real headings like:
        - "CHAPTER 1"
        - "CHAPTER I"
        - "INTRODUCTION"
        - "PROLOGUE"
        """

        # Never treat dotted-leader TOC lines as body headings.
        if contains_dotted_leader(line):
            return False

        for pat in (
            re.compile(r"(?im)^\s*introduction\s*$"),
            re.compile(
                r"(?im)^\s*(foreword|preface|acknowledgements?|acknowledgments)\s*$",
            ),
            re.compile(r"(?im)^\s*prologue\s*$"),
            # Chapter headings may include number/roman numeral.
            re.compile(
                r"(?im)^\s*(?:\d+(?:\.\d+)*)?\s*chapter\s+(?:1|i)\b"
                r"(?!.*\.{2,})(?:\s*$|\s*[.:\-–—]\s*\S+)"
            ),
        ):
            if pat.match(line):
                return True

        return False

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
