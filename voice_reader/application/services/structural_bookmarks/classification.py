from __future__ import annotations

import re

from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
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
BOOK_RE = re.compile(
    r"^(book)\s+(?P<num>[0-9ivxlcdm]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)
CH_DOT_RE = re.compile(r"^(ch\.)\s*(?P<num>[0-9ivxlcdm]+)\b.*$", re.IGNORECASE)

# Some books (including technical monographs) structure major sections as
# "Axiom N: ..." rather than "Chapter N".
AXIOM_RE = re.compile(
    r"^(axiom)\s+(?P<num>[0-9ivxlcdm]+)\b(\s*[:\-\u2013]\s+.+)?$",
    re.IGNORECASE,
)


def classify_heading(label: str) -> tuple[str | None, bool, int]:
    """Classify a heading label.

    Returns:
        (kind, include, priority)

    priority is used for tie-breaking/dedup when multiple sources disagree.
    Higher priority wins.
    """

    # Clean PDF TOC artifacts (leaders/page numbers) before classification.
    raw = clean_heading_label(label)
    if not raw:
        raw = normalize_label_for_match(label)
    s = raw.casefold()

    def _looks_like_title_case_section(text: str) -> bool:
        # Heuristic: accept title-case-ish headings that look like TOC/body chapter
        # titles even when the book doesn't label them as "Chapter N".
        t = str(text or "").strip()
        if not t:
            return False
        if len(t) < 6 or len(t) > 90:
            return False
        if t.endswith((".", "!", "?", ";")):
            return False
        # Avoid common "micro" headings that would flood the Sections list.
        micro = {
            "notation",
            "physical",
            "decision-system mapping",
            "decision system mapping",
            "relationship / equation",
            "constraint",
            "implication",
            "observable / measurement (even if partial)",
            "observable / measurement",
        }
        if t.casefold() in micro:
            return False

        # Require at least 2 words to avoid single-word subheadings.
        words = [w for w in re.split(r"\s+", t) if w]
        if len(words) < 2 or len(words) > 10:
            return False

        stop = {
            "a",
            "an",
            "and",
            "as",
            "at",
            "by",
            "for",
            "from",
            "in",
            "into",
            "is",
            "of",
            "on",
            "or",
            "the",
            "to",
            "with",
            "without",
        }

        def _is_titleish(w: str) -> bool:
            w0 = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", w)
            if not w0:
                return True
            if w0.casefold() in stop:
                return True
            # allow acronyms / initialisms
            if len(w0) >= 2 and w0.isupper():
                return True
            return w0[:1].isupper()

        titleish = sum(1 for w in words if _is_titleish(w))
        # Must be mostly title-like.
        if titleish / max(1, len(words)) < 0.75:
            return False

        # Avoid lines that contain obvious equation-ish tokens.
        if re.search(r"[=<>]{1,2}", t):
            return False
        return True

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

    if BOOK_RE.match(raw):
        return "book", True, 72

    if CHAPTER_RE.match(raw) or CH_DOT_RE.match(raw):
        return "chapter", True, 60

    if AXIOM_RE.match(raw):
        return "axiom", True, 60

    if _looks_like_title_case_section(raw):
        return "section", True, 40

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
