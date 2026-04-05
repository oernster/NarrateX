from __future__ import annotations

import re

from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
    normalize_label_for_compare,
)
from voice_reader.domain.entities.structural_bookmark import StructuralBookmark


_CHAPTER_OR_PART_PREFIX_RE = re.compile(
    r"(?i)^(chapter|part)\s+[0-9ivxlcdm]+\s*(?:[:\-\u2013\u2014])?\s*(?P<rest>.*)$"
)


def suppress_redundant_title_sections(
    *,
    bookmarks: list[StructuralBookmark],
) -> list[StructuralBookmark]:
    """Remove redundant 'section' entries that duplicate a preceding chapter/part.

    Some EPUB/PDF extractions emit headings like:
      Chapter 1: These Are Not Examples
      These Are Not Examples

    The second line is typically a duplicate of the chapter title. Keeping both
    clutters the Sections list and can confuse play-from-scratch selection.
    """

    out: list[StructuralBookmark] = []
    for b in bookmarks:
        if (
            out
            and str(b.kind) == "section"
            and str(out[-1].kind) in {"chapter", "part"}
        ):
            prev = out[-1]
            try:
                close = abs(int(b.char_offset) - int(prev.char_offset)) <= 160
            except Exception:
                close = False
            if close:
                prev_lab = clean_heading_label(str(prev.label or "").strip()) or str(
                    prev.label or ""
                ).strip()
                m = _CHAPTER_OR_PART_PREFIX_RE.match(prev_lab)
                rest = str(m.group("rest") or "").strip() if m is not None else ""
                if rest and normalize_label_for_compare(rest) == normalize_label_for_compare(
                    str(b.label or "")
                ):
                    continue

        out.append(b)

    return out


def suppress_sections_between_chapters(
    *,
    bookmarks: list[StructuralBookmark],
) -> list[StructuralBookmark]:
    """Drop unlabelled title-case 'section' headings that occur between chapters.

    Some books include occasional in-chapter subheadings that look like major
    sections (title case, surrounded by blanks). When a document already has
    explicit Chapter structure, these tend to be noise in the Sections UI.
    """

    chapter_count = sum(1 for b in bookmarks if str(b.kind) == "chapter")
    if chapter_count < 2:
        return bookmarks

    out: list[StructuralBookmark] = []
    for i, b in enumerate(bookmarks):
        if str(b.kind) == "section":
            prev_kind = str(bookmarks[i - 1].kind) if i > 0 else ""
            next_kind = str(bookmarks[i + 1].kind) if i + 1 < len(bookmarks) else ""
            if prev_kind == "chapter" and next_kind == "chapter":
                continue
        out.append(b)

    return out


def inject_prologue_after_each_book(
    *,
    bookmarks: list[StructuralBookmark],
    normalized_text: str,
    max_distance: int = 40_000,
) -> list[StructuralBookmark]:
    """Ensure each `book` marker is followed by its own `prologue` when present.

    In omnibus-style PDFs/EPUBs, multiple books can be concatenated into a single
    file. Headings like "Prologue" then appear multiple times. Our base pipeline
    dedupes by label, which would otherwise collapse all "Prologue" headings into
    one bookmark.
    """

    books = [b for b in bookmarks if str(b.kind) == "book"]
    if not books:
        return bookmarks

    text = str(normalized_text or "")
    if not text:
        return bookmarks

    prologue_offsets = [m.start() for m in re.finditer(r"(?m)^\s*Prologue\s*$", text)]
    if not prologue_offsets:
        return bookmarks

    out = list(bookmarks)
    books_sorted = sorted(books, key=lambda b: int(b.char_offset))
    for i, book in enumerate(books_sorted):
        start = int(book.char_offset)
        end = (
            int(books_sorted[i + 1].char_offset)
            if (i + 1) < len(books_sorted)
            else len(text) + 1
        )
        if any(
            str(b.kind) == "prologue" and start < int(b.char_offset) < end
            for b in bookmarks
        ):
            continue

        cand = next((o for o in prologue_offsets if start < int(o) < end), None)
        if cand is None:
            continue
        if int(cand) - int(start) > int(max_distance):
            continue

        out.append(
            StructuralBookmark(
                label="Prologue",
                char_offset=int(cand),
                chunk_index=None,
                kind="prologue",
                level=0,
            )
        )

    out.sort(key=lambda b: int(b.char_offset))
    return out

