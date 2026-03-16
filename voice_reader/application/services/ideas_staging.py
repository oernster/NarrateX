"""Ideas input staging helpers.

Purpose
-------
On Windows, multiprocessing `spawn` pickles the parent-side arguments during
process startup. Passing large in-memory `normalized_text` through the spawn
payload can block the UI thread if the caller is a Qt slot.

This module stages large text inputs to an app-managed writable directory and
returns a lightweight file-path reference that can be passed to a worker.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def _safe_stem(*, book_id: str) -> str:
    raw = str(book_id or "").strip()
    if not raw:
        return "book"
    # Keep filenames stable-ish and cross-platform safe.
    out = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    # The join below already has a safe fallback; keep this branch for readability.
    return "".join(out)[:80] or "book"


def stage_normalized_text(
    *,
    work_dir: Path,
    book_id: str,
    normalized_text: str,
) -> Path:
    """Write normalized text to a staged file and return its path.

    The write is best-effort atomic: write to a temporary file in the same
    directory, then replace.
    """

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(book_id=str(book_id))
    final_path = (work_dir / f"{stem}.{uuid.uuid4().hex}.normalized.txt").resolve()
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")

    # Use newline normalization as-is; the input is already normalized upstream.
    data = str(normalized_text or "")
    tmp_path.write_text(data, encoding="utf-8", errors="replace")
    os.replace(tmp_path, final_path)
    return final_path


def safe_unlink(path: str | Path | None) -> None:
    """Best-effort removal for staged inputs."""

    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:  # pragma: no cover
        return

