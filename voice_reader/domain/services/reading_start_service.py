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
    """Detect the character offset to begin narration."""

    max_scan_chars: int = 60000
    max_prose_seek_chars: int = 40000

    def detect_start(self, text: str) -> ReadingStart:
        scan = text[: self.max_scan_chars]

        candidates: list[ReadingStart] = []

        # Introduction
        for m in re.finditer(r"(?im)^\s*introduction\s*$", scan):
            candidates.append(
                ReadingStart(
                    start_char=self._start_after_heading(scan, m.end()),
                    reason="Detected Introduction",
                )
            )
            break

        # Foreword / Preface / Acknowledgements
        for pat in self._frontmatter_patterns():
            for m in pat.finditer(scan):
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, m.end()),
                        reason="Detected Frontmatter",
                    )
                )
                break

        # Chapter 1
        for pat in self._chapter_one_patterns():
            for m in pat.finditer(scan):
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, m.end()),
                        reason="Detected Chapter 1",
                    )
                )
                break

        # Prologue
        for pat in self._prologue_patterns():
            for m in pat.finditer(scan):
                candidates.append(
                    ReadingStart(
                        start_char=self._start_after_heading(scan, m.end()),
                        reason="Detected Prologue",
                    )
                )
                break

        # Fallback: skip ToC
        if not candidates:
            toc_end = self._detect_toc_end(scan)
            if toc_end is not None:
                candidates.append(
                    ReadingStart(
                        start_char=toc_end,
                        reason="Skipped Table of Contents",
                    )
                )

        best = self._pick_best(candidates)

        if best is None:
            return ReadingStart(start_char=0, reason="Start at beginning")

        start = self._skip_leading_whitespace(text, best.start_char)
        start = self._seek_first_paragraph(text, start)

        return ReadingStart(start_char=start, reason=best.reason)

    def _seek_first_paragraph(self, text: str, start: int) -> int:
        """Find the first real prose paragraph."""

        end = min(len(text), start + self.max_prose_seek_chars)
        window = text[start:end]

        offset = start

        for line in window.splitlines():

            stripped = line.strip()

            if not stripped:
                offset += len(line) + 1
                continue

            if self._looks_like_structure(stripped):
                offset += len(line) + 1
                continue

            if self._looks_like_backmatter(stripped):
                return start

            if self._looks_like_paragraph(stripped):
                return self._skip_leading_whitespace(text, offset)

            offset += len(line) + 1

        return start

    @staticmethod
    def _looks_like_paragraph(line: str) -> bool:

        words = [w for w in re.split(r"\s+", line) if w]

        if len(words) < 3:
            return False

        if not any(ch.islower() for ch in line):
            return False

        if re.search(r"[.!?]\s*$", line):
            return True

        if len(words) >= 14 or len(line) >= 90:
            return True

        return False

    @staticmethod
    def _looks_like_structure(line: str) -> bool:

        # dotted TOC leaders
        if re.search(r"\.{2,}\s*\d+\s*$", line):
            return True

        # trailing page numbers
        if re.search(r"\s\d+\s*$", line) and len(line) < 60:
            return True

        # roman page numbers
        if re.match(r".+\s+[ivxlcdm]+\s*$", line, re.I):
            return True

        # outline numbering
        if re.match(r"^\d+(?:\.\d+)*$", line):
            return True

        # numbered headings like "4.2 Chapter title"
        if re.match(r"^\d+(?:\.\d+)*\s+\S+", line):
            return True

        # short section titles typical of TOC entries
        words = line.split()
        if len(words) <= 8 and not re.search(r"[.!?]", line):
            return True

        # titles that follow numeric sections like
        # "The symptom often looks like this."
        # which appear in ToCs under numbering
        if len(words) <= 10 and re.match(r"^[A-Z]", line):
            return True

        # title page / copyright / dedication
        if re.match(r"(?i)^\s*(copyright|all rights reserved)\b", line):
            return True

        if re.match(r"(?i)^\s*dedication\b", line):
            return True

        return False`

    @staticmethod
    def _looks_like_backmatter(line: str) -> bool:
        """Detect end-of-book sections."""

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

        if not candidates:
            return None

        intro = [c for c in candidates if "Introduction" in c.reason]
        if intro:
            return min(intro, key=lambda c: c.start_char)

        front = [c for c in candidates if "Frontmatter" in c.reason]
        if front:
            return min(front, key=lambda c: c.start_char)

        ch1 = [c for c in candidates if "Chapter 1" in c.reason]
        if ch1:
            return min(ch1, key=lambda c: c.start_char)

        pro = [c for c in candidates if "Prologue" in c.reason]
        if pro:
            return min(pro, key=lambda c: c.start_char)

        return min(candidates, key=lambda c: c.start_char)

    @staticmethod
    def _start_after_heading(text: str, idx: int) -> int:

        line_end = text.find("\n", idx)

        if line_end == -1:
            return len(text)

        i = line_end + 1

        while i < len(text) and text[i].isspace():
            i += 1

        return i

    @staticmethod
    def _detect_toc_end(scan: str) -> int | None:

        toc = re.search(r"(?im)^\s*(table of contents|contents)\s*$", scan)

        if not toc:
            return None

        start = toc.end()

        lines = scan[start:].splitlines(keepends=True)

        offset = start
        consumed = False

        for line in lines:

            stripped = line.strip()

            if not stripped:
                offset += len(line)
                continue

            if ReadingStartService._looks_like_structure(stripped):
                consumed = True
                offset += len(line)
                continue

            if consumed:
                break

            return None

        return offset if consumed else None

    @staticmethod
    def _chapter_one_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*chapter\s+1\b"),
            re.compile(r"(?im)^\s*chapter\s+i\b"),
            re.compile(r"(?im)^\s*ch\.\s*1\b"),
        ]

    @staticmethod
    def _prologue_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*prologue\b"),
        ]

    @staticmethod
    def _frontmatter_patterns() -> list[re.Pattern[str]]:
        return [
            re.compile(r"(?im)^\s*foreword\b"),
            re.compile(r"(?im)^\s*preface\b"),
            re.compile(r"(?im)^\s*acknowledgements?\b"),
            re.compile(r"(?im)^\s*acknowledgments\b"),
        ]