from __future__ import annotations

import re

STOPWORDS = {
    "the",
    "and",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "from",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "it",
    "that",
    "this",
    "these",
    "those",
    "i",
    "you",
    "we",
    "they",
    "he",
    "she",
    "not",
    "or",
    "but",
    "if",
    "then",
    "so",
    "no",
    "yes",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text) if t]


def extract_top_concepts(*, text: str, max_concepts: int = 5) -> list[tuple[str, int]]:
    """Return [(label, first_occurrence_offset), ...] small/bounded concepts."""

    tokens = tokenize(text)
    freq: dict[str, int] = {}
    first: dict[str, int] = {}
    lowered_text = text.lower()

    for t in tokens:
        k = t.lower()
        if k in STOPWORDS:
            continue
        if len(k) < 3:  # pragma: no cover
            continue
        freq[k] = freq.get(k, 0) + 1
        if k not in first:
            # Token comes from the same text; ValueError is not expected.
            first[k] = int(lowered_text.index(k))

    ranked = sorted(freq.items(), key=lambda kv: (-int(kv[1]), kv[0]))
    out: list[tuple[str, int]] = []
    for k, _count in ranked[: int(max_concepts)]:
        label = k.replace("-", " ").title()
        out.append((label, int(first.get(k, 0))))

    out.sort(key=lambda t: int(t[1]))
    return out
