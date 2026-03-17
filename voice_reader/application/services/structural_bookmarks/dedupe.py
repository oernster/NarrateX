from __future__ import annotations

from typing import Sequence

from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_label_for_compare,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)


def is_early_front_matter_exclusion(
    *,
    normalized_label: str,
    char_offset: int,
    total_chars: int,
) -> bool:
    """Extra practical rule: exclude index-like headings very early in the book."""

    if total_chars <= 0:
        return False
    frac = float(char_offset) / float(total_chars)
    if frac > 0.05:
        return False

    early_excludes = {
        "contents",
        "table of contents",
        "essay index",
        "pattern index",
        "index",
        "summary",
        "summaries",
    }
    return normalized_label in early_excludes


def dedupe_candidates(
    *, candidates: Sequence[RawHeadingCandidate]
) -> list[RawHeadingCandidate]:
    """Deduplicate near-identical heading candidates."""

    def source_rank(src: str) -> int:
        s = str(src or "").casefold()
        if s in {"nav", "chapter_parser", "chapter", "parser"}:
            return 30
        if s == "text_scan":
            return 10
        return 20

    groups: dict[str, list[RawHeadingCandidate]] = {}
    for c in candidates:
        key = normalize_label_for_compare(c.label)
        if not key:
            continue
        groups.setdefault(key, []).append(c)

    kept: list[RawHeadingCandidate] = []
    for _, group in groups.items():
        # For a single label, we may legitimately have multiple occurrences far
        # apart. We cluster by proximity (<= 400 chars).

        # Prefer candidates with known offsets; sort by offset (unknown last).
        group_by_offset = sorted(
            group,
            key=lambda c: c.char_offset if c.char_offset is not None else 10**18,
        )

        clusters: list[list[RawHeadingCandidate]] = []
        for cand in group_by_offset:
            if cand.char_offset is None:
                # Offset-less candidates can't be clustered reliably; treat each
                # as its own cluster (tie-breaking will pick the best).
                clusters.append([cand])
                continue

            if not clusters:
                clusters.append([cand])
                continue

            last = clusters[-1][-1]
            if last.char_offset is None:
                clusters.append([cand])
                continue

            if abs(int(cand.char_offset) - int(last.char_offset)) <= 400:
                clusters[-1].append(cand)
            else:
                clusters.append([cand])

        def best_in_cluster(
            cluster: Sequence[RawHeadingCandidate],
        ) -> RawHeadingCandidate:
            # Higher is better.
            def score(c: RawHeadingCandidate) -> tuple[int, int, int, int]:
                return (
                    1 if c.char_offset is not None else 0,
                    source_rank(c.source),
                    1 if c.chunk_index is not None else 0,
                    -int(c.char_offset) if c.char_offset is not None else 0,
                )

            return sorted(cluster, key=score, reverse=True)[0]

        for cluster in clusters:
            kept.append(best_in_cluster(cluster))

    return list(kept)
