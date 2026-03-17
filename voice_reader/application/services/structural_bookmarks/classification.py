from __future__ import annotations

import re

from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_label_for_match,
)

# Strong heading patterns (should be accepted even if not surrounded by blanks).
PART_RE = re.compile(
    r"^(part)\s+(?P<num>[ivxlcdm0-9]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)
CHAPTER_RE = re.compile(
    r"^(chapter)\s+(?P<num>[0-9ivxlcdm]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)
CH_DOT_RE = re.compile(r"^(ch\.)\s*(?P<num>[0-9ivxlcdm]+)\b.*$", re.IGNORECASE)


def classify_heading(label: str) -> tuple[str | None, bool, int]:
    """Classify a heading label.

    Returns:
        (kind, include, priority)

    priority is used for tie-breaking/dedup when multiple sources disagree.
    Higher priority wins.
    """

    raw = normalize_label_for_match(label)
    s = raw.casefold()

    # Explicit exclusions (front matter/junk).
    excludes = [
        r"^contents$",
        r"^table of contents$",
        r"^essay index$",
        r"^pattern index$",
        r"^index$",
        r"^summary$",
        r"^summaries$",
        r"^about me$",
        r"^copyright$",
        r"^title page$",
        r"^acknowledg(e)?ments$",
        r"^dedication$",
    ]
    for pat in excludes:
        if re.search(pat, s, flags=re.IGNORECASE):
            return None, False, 0

    # Inclusion patterns.
    if re.fullmatch(r"prologue", s, flags=re.IGNORECASE):
        return "prologue", True, 90

    if re.fullmatch(r"(introduction|intro|about this book)", s, flags=re.IGNORECASE):
        return "introduction", True, 80

    if re.fullmatch(r"preface", s, flags=re.IGNORECASE):
        return "preface", True, 75

    if PART_RE.match(raw):
        return "part", True, 70

    if CHAPTER_RE.match(raw) or CH_DOT_RE.match(raw):
        return "chapter", True, 60

    if re.match(r"^appendix\b", s, flags=re.IGNORECASE):
        return "appendix", True, 55

    if re.fullmatch(r"epilogue", s, flags=re.IGNORECASE):
        return "epilogue", True, 50

    if re.fullmatch(
        r"(conclusion|closing observation|closing reflections?)",
        s,
        flags=re.IGNORECASE,
    ):
        return "conclusion", True, 50

    if re.fullmatch(r"afterword", s, flags=re.IGNORECASE):
        return "afterword", True, 45

    return None, False, 0
