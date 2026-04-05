from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.types import HeadingOccurrence
from voice_reader.application.text_patterns import contains_dotted_leader, normalize_dotlikes


@dataclass(frozen=True, slots=True)
class HeadingOccurrenceIndex:
    """One-pass heading occurrence index for a single document.

    Motivation: [`find_exact_heading_occurrences()`](voice_reader/application/services/structural_bookmarks/occurrences.py:21)
    scans the entire document per label. On omnibus PDFs with 100+ labels, that can
    become slow enough to appear as a UI hang.

    This index scans the document once and stores matches for a *set* of desired
    normalized labels.
    """

    exact: dict[str, list[HeadingOccurrence]]
    wrapped: dict[str, list[HeadingOccurrence]]
    prefix: dict[str, list[HeadingOccurrence]]

    @staticmethod
    def build(
        *,
        normalized_text: str,
        wanted_norm_labels: Iterable[str],
        min_char_offset: int = 0,
    ) -> "HeadingOccurrenceIndex":
        text = str(normalized_text or "")
        wanted = {str(x) for x in (wanted_norm_labels or []) if str(x)}
        if not text or not wanted:
            return HeadingOccurrenceIndex(exact={}, wrapped={}, prefix={})

        min_off = max(0, int(min_char_offset))
        lines = text.splitlines(keepends=True)
        stripped_lines = [ln.strip() for ln in lines]
        is_blank = [not s for s in stripped_lines]

        # Precompute line offsets.
        line_offsets: list[int] = []
        off = 0
        for ln in lines:
            line_offsets.append(int(off))
            off += len(ln)

        # Precompute nearest nonblank indices for lookups.
        prev_nb_idx: list[int | None] = [None] * len(lines)
        last: int | None = None
        for i in range(len(lines)):
            prev_nb_idx[i] = last
            if not is_blank[i]:
                last = int(i)

        next_nb_idx: list[int | None] = [None] * len(lines)
        nxt: int | None = None
        for i in range(len(lines) - 1, -1, -1):
            next_nb_idx[i] = nxt
            if not is_blank[i]:
                nxt = int(i)

        outline_only_re = re.compile(r"\d+(?:\.\d+)*$")
        page_only_re = re.compile(r"^(\d+|[ivxlcdm]+)$", flags=re.I)

        def _looks_like_outline_number_only(s: str) -> bool:
            return bool(outline_only_re.fullmatch(str(s or "").strip()))

        def _is_leader_only(s: str) -> bool:
            s2 = normalize_dotlikes(str(s or "")).strip()
            return bool(contains_dotted_leader(s2) and re.fullmatch(r"[.\s]+", s2))

        def _is_probable_toc_occurrence(i: int, stripped_line: str) -> bool:
            # Mirror logic from `find_exact_heading_occurrences()`.
            if contains_dotted_leader(stripped_line):
                return True

            prev_i = prev_nb_idx[i]
            if prev_i is not None:
                prev_s = stripped_lines[int(prev_i)]
                if _looks_like_outline_number_only(prev_s):
                    # Look ahead for leader/page evidence.
                    look: list[str] = []
                    j = int(i) + 1
                    while j < len(lines) and len(look) < 4:
                        v = stripped_lines[j]
                        if v:
                            look.append(v)
                        j += 1
                    if any(_is_leader_only(v) or contains_dotted_leader(v) for v in look):
                        return True
                    if any(page_only_re.fullmatch(v) for v in look) and any(
                        _is_leader_only(v) or contains_dotted_leader(v) for v in look
                    ):
                        return True

            look2: list[str] = []
            j2 = int(i) + 1
            while j2 < len(lines) and len(look2) < 4:
                v = stripped_lines[j2]
                if v:
                    look2.append(v)
                j2 += 1
            if any(_is_leader_only(v) for v in look2):
                return True

            return False

        exact: dict[str, list[HeadingOccurrence]] = {}
        wrapped: dict[str, list[HeadingOccurrence]] = {}
        prefix: dict[str, list[HeadingOccurrence]] = {}

        for i, stripped in enumerate(stripped_lines):
            line_offset = int(line_offsets[i])
            if line_offset < min_off:
                continue
            if not stripped:
                continue

            cleaned_line = clean_heading_label(stripped) or stripped
            cleaned_cmp = normalize_label_for_compare(cleaned_line)

            probable_toc = _is_probable_toc_occurrence(i, stripped_line=stripped)
            prev_blank = True if i <= 0 else bool(is_blank[i - 1])
            next_blank = True if (i + 1) >= len(lines) else bool(is_blank[i + 1])

            if not probable_toc and cleaned_cmp in wanted:
                exact.setdefault(cleaned_cmp, []).append(
                    HeadingOccurrence(
                        char_offset=line_offset,
                        label=clean_heading_label(stripped)
                        or normalize_label_for_match(stripped),
                        prev_blank=prev_blank,
                        next_blank=next_blank,
                    )
                )

            # Wrapped-heading detection: current + next nonblank line.
            nb_next = next_nb_idx[i]
            if nb_next is not None:
                nxt_s = stripped_lines[int(nb_next)]
                if nxt_s:
                    joined = (
                        f"{stripped[:-1]}{nxt_s}" if stripped.endswith("-") else f"{stripped} {nxt_s}"
                    )
                    joined_clean = clean_heading_label(joined) or normalize_label_for_match(
                        joined
                    )
                    joined_cmp = normalize_label_for_compare(joined_clean)
                    if (not probable_toc) and joined_cmp in wanted:
                        wrapped.setdefault(joined_cmp, []).append(
                            HeadingOccurrence(
                                char_offset=line_offset,
                                label=joined_clean,
                                prev_blank=prev_blank,
                                next_blank=next_blank,
                            )
                        )

            # Prefix fallback: treat "Chapter N" / "Part N" marker lines as anchors.
            if not probable_toc and cleaned_cmp:
                kind2, include2, _p2 = classify_heading(cleaned_line)
                if include2 and kind2 in {"chapter", "part"}:
                    prefix.setdefault(cleaned_cmp, []).append(
                        HeadingOccurrence(
                            char_offset=line_offset,
                            label=clean_heading_label(stripped)
                            or normalize_label_for_match(stripped),
                            prev_blank=prev_blank,
                            next_blank=next_blank,
                        )
                    )

        return HeadingOccurrenceIndex(exact=exact, wrapped=wrapped, prefix=prefix)

    def occurrences_for(
        self,
        *,
        cleaned_label: str,
        prefix_norm: str | None,
    ) -> list[HeadingOccurrence]:
        """Return occurrences using the same precedence rules as the legacy scan."""

        norm_label = normalize_label_for_compare(cleaned_label)
        if not norm_label:
            return []

        out = self.exact.get(norm_label) or []
        if out:
            return out

        wrapped = self.wrapped.get(norm_label) or []
        if wrapped:
            return wrapped

        if prefix_norm:
            pref = self.prefix.get(prefix_norm) or []
            if pref:
                return pref

        return []

    def occurrences_for_label(self, *, label: str) -> list[HeadingOccurrence]:
        """Return occurrences for `label` using legacy precedence rules.

        This mirrors [`find_exact_heading_occurrences()`](voice_reader/application/services/structural_bookmarks/occurrences.py:21)
        but uses the one-pass index.
        """

        cleaned = clean_heading_label(label)
        cleaned_label = cleaned or str(label or "")

        prefix_norm: str | None = None
        try:
            m = re.match(
                r"^(chapter|part|book)\s+(?P<num>[0-9ivxlcdm]+)\b",
                str(cleaned_label or "").strip(),
                flags=re.IGNORECASE,
            )
            if m is not None and (
                (":" in str(cleaned_label)) or ("-" in str(cleaned_label))
            ):
                prefix = f"{m.group(1)} {m.group('num')}"
                prefix_norm = normalize_label_for_compare(
                    clean_heading_label(prefix) or prefix
                )
        except Exception:
            prefix_norm = None

        return self.occurrences_for(cleaned_label=cleaned_label, prefix_norm=prefix_norm)

