from __future__ import annotations

from voice_reader.application.services.structural_bookmarks.classification import (
    classify_heading,
)
from voice_reader.application.services.structural_bookmarks.normalization import (
    clean_heading_label,
    normalize_label_for_compare,
    normalize_label_for_match,
)
from voice_reader.application.services.structural_bookmarks.text_scan import (
    scan_structural_headings,
)


def extract_heading_labels_from_text(*, normalized_text: str) -> list[str]:
    """Return unique structural heading labels found by scanning the text."""

    labels: list[str] = []
    seen: set[str] = set()
    for c in scan_structural_headings(normalized_text=str(normalized_text or "")):
        lab = clean_heading_label(c.label) or normalize_label_for_match(c.label)
        if not lab:
            continue
        kind, include, _priority = classify_heading(lab)
        if not include or kind is None:
            continue
        key = normalize_label_for_compare(lab)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return labels

