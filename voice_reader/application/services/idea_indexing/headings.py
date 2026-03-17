from __future__ import annotations

import re

_CHAPTER_RE = re.compile(
    r"(?im)^[ \t]*chapter\b[ \t]+(?P<num>\d+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_PART_RE = re.compile(
    r"(?im)^[ \t]*part\b[ \t]+(?P<num>\d+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def iter_lines_with_offsets(text: str):
    """Yield (line_text, line_start_offset) pairs for `text`."""

    start = 0
    for m in re.finditer(r"\n", text):
        end = m.start()
        yield text[start:end], start
        start = m.end()
    yield text[start:], start


def is_reasonable_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if len(s) < 3 or len(s) > 80:
        return False
    if s.endswith("."):
        return False
    if not any(ch.isalpha() for ch in s):  # pragma: no cover
        return False
    # Avoid shouting or very noisy lines.
    if s.count(":") > 1:  # pragma: no cover
        return False
    return True


def detect_headings(*, text: str, max_headings: int = 50) -> list[tuple[str, int]]:
    """Return [(label, char_offset), ...] conservative heading candidates."""

    out: list[tuple[str, int]] = []
    for line, off in iter_lines_with_offsets(text):
        raw = line.rstrip("\r")
        if not is_reasonable_heading(raw):
            continue
        s = raw.strip()

        # Strong signals.
        if _CHAPTER_RE.match(s) or _PART_RE.match(s):
            out.append((s, int(off)))
            continue

        # Weak signal: short title-case line surrounded by whitespace.
        words = [w for w in re.split(r"\s+", s) if w]
        if 1 <= len(words) <= 8:
            titleish = sum(1 for w in words if w[:1].isupper())
            if titleish >= max(1, len(words) // 2):
                out.append((s, int(off)))

        if len(out) >= int(max_headings):  # pragma: no cover
            break

    # Preserve text order, drop duplicates by (label, offset).
    seen: set[tuple[str, int]] = set()
    unique: list[tuple[str, int]] = []
    for item in out:
        if item in seen:  # pragma: no cover
            # Defensive: duplicates by (label, offset) should not occur because
            # `offset` is line-start specific.
            continue
        seen.add(item)
        unique.append(item)
    unique.sort(key=lambda t: int(t[1]))
    return unique
