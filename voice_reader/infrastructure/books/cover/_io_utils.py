from __future__ import annotations

from pathlib import Path

# A picture past this size is not a cover. It bounds what a cover read may
# allocate wherever the bytes come from: an image beside the book or an entry
# inside an EPUB, whose stated size is checked before it is decompressed.
MAX_COVER_BYTES = 12 * 1024 * 1024


def safe_read_image_bytes(
    path: Path,
    *,
    max_bytes: int | None,
) -> bytes | None:
    """Read bytes from an image file path, with an optional size guard."""

    try:
        if not path.exists() or not path.is_file():
            return None
        if max_bytes is not None:
            try:
                if path.stat().st_size > int(max_bytes):
                    return None
            except Exception:
                # If we can't stat it, we also shouldn't try reading it.
                return None
        return path.read_bytes()
    except Exception:
        return None
