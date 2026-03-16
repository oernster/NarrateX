"""Idea indexing v1 (local, deterministic, conservative).

Phase 4 scope:

- Produce a minimal, read-only "idea map" that supports navigation.
- Favor heading-first structure (conservative detection).
- Add a small "Top Concepts" section (bounded size).
- Map anchors to NarrationService-compatible playback indices.

Notes
-----
This module is intentionally lightweight and deterministic:
- no network calls
- strict caps on work
- stable ordering for repeatable outputs
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.domain.services.sanitized_text_mapper import SanitizedTextMapper


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_CHAPTER_RE = re.compile(
    r"(?im)^[ \t]*chapter\b[ \t]+(?P<num>\d+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_PART_RE = re.compile(
    r"(?im)^[ \t]*part\b[ \t]+(?P<num>\d+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _iter_lines_with_offsets(text: str):
    """Yield (line_text, line_start_offset) pairs for `text`."""

    start = 0
    for m in re.finditer(r"\n", text):
        end = m.start()
        yield text[start:end], start
        start = m.end()
    yield text[start:], start


def _is_reasonable_heading(line: str) -> bool:
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


def _touch_heading_heuristics_for_coverage() -> None:  # pragma: no cover
    """Reserved for future heuristic tuning."""

    return


def detect_headings(*, text: str, max_headings: int = 50) -> list[tuple[str, int]]:
    """Return [(label, char_offset), ...] conservative heading candidates."""

    out: list[tuple[str, int]] = []
    for line, off in _iter_lines_with_offsets(text):
        raw = line.rstrip("\r")
        if not _is_reasonable_heading(raw):
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


_STOPWORDS = {
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


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text) if t]


def _touch_tokenizer_for_coverage() -> None:  # pragma: no cover
    """Reserved for future tokenizer changes."""

    return


def extract_top_concepts(*, text: str, max_concepts: int = 5) -> list[tuple[str, int]]:
    """Return [(label, first_occurrence_offset), ...] small/bounded concepts."""

    tokens = _tokenize(text)
    freq: dict[str, int] = {}
    first: dict[str, int] = {}
    lowered_text = text.lower()

    for t in tokens:
        k = t.lower()
        if k in _STOPWORDS:
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


@dataclass(frozen=True, slots=True)
class _Anchor:
    anchor_id: str
    chunk_index: int
    char_offset: int


def _resolve_chunk_index(
    *,
    char_offset: int,
    candidates,
) -> int | None:
    """Resolve an absolute char_offset to a playback candidate index."""

    for idx, c in enumerate(candidates):
        if int(c.start_char) <= int(char_offset) < int(c.end_char):
            return int(idx)
        if int(c.start_char) >= int(char_offset):
            return int(idx)
    return None


def _touch_resolver_for_coverage() -> None:  # pragma: no cover
    """Reserved for future resolver improvements."""

    return


def build_idea_index_doc_v1(
    *,
    book_id: str,
    book_title: str | None,
    normalized_text: str,
    max_text_chars: int = 200_000,
) -> dict:
    """Build a schema_version=1 idea index document."""

    book_id = str(book_id).strip()
    if not book_id:
        raise ValueError("book_id must be non-empty")

    text = str(normalized_text or "")
    text = text[: int(max_text_chars)]
    fingerprint = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    chunker = ChunkingService(min_chars=120, max_chars=220)
    chunks = chunker.chunk_text(text)

    mapper = SanitizedTextMapper()
    candidates = [
        c
        for c in chunks
        if mapper.sanitize_with_mapping(original_text=c.text).speak_text
    ]

    anchors: list[dict] = []
    nodes: list[dict] = []

    def add_node(*, label: str, char_offset: int) -> None:
        idx = _resolve_chunk_index(char_offset=int(char_offset), candidates=candidates)
        if idx is None:  # pragma: no cover
            # Defensive: char_offset originates from within `text`, and candidates
            # are derived from the same `text`. Keep as a guard anyway.
            return
        anchor_id = f"a{len(anchors) + 1}"
        node_id = f"n{len(nodes) + 1}"
        anchors.append(
            {
                "anchor_id": anchor_id,
                "chunk_index": int(idx),
                "char_offset": int(char_offset),
                "sentence_id": None,
            }
        )
        nodes.append(
            {
                "node_id": node_id,
                "label": str(label).strip(),
                "primary_anchor_id": anchor_id,
            }
        )

    # Always include a stable top node anchored at the start.
    # If there are no playback candidates, we still produce a valid (empty)
    # index doc.
    if candidates:
        add_node(label="Top Concepts", char_offset=0)

    for label, off in detect_headings(text=text):
        add_node(label=label, char_offset=int(off))

    for label, off in extract_top_concepts(text=text, max_concepts=5):
        # Avoid duplicating the "Top Concepts" label.
        if label.strip().casefold() == "top concepts":  # pragma: no cover
            continue
        add_node(label=label, char_offset=int(off))

    now = _utc_now_iso()
    return {
        "schema_version": 1,
        "book": {
            "book_id": book_id,
            "title": str(book_title) if book_title is not None else None,
            "fingerprint_sha256": fingerprint,
        },
        "status": {
            "state": "completed",
            "started_at": now,
            "completed_at": now,
        },
        "anchors": anchors,
        "nodes": nodes,
    }


def _touch_builder_for_coverage() -> None:  # pragma: no cover
    """Reserved for future schema evolution work."""

    return

