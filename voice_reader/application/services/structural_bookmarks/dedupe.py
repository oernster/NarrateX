from __future__ import annotations

from typing import Sequence

from voice_reader.application.services.structural_bookmarks.normalization import (
    normalize_label_for_compare,
)
from voice_reader.application.services.structural_bookmarks.types import (
    RawHeadingCandidate,
)

# Two candidates for the same label are the same heading when they sit this
# close together; further apart they are separate occurrences.
CLUSTER_DISTANCE_CHARS = 400

# Candidates with no offset cannot be ordered, so they sort after every real
# one. Any offset at or above this behaves as though it had no offset at all.
UNKNOWN_OFFSET_SORT_KEY = 10**18


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
            key=lambda c: (
                c.char_offset if c.char_offset is not None else UNKNOWN_OFFSET_SORT_KEY
            ),
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

            if (
                abs(int(cand.char_offset) - int(last.char_offset))
                <= CLUSTER_DISTANCE_CHARS
            ):
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
