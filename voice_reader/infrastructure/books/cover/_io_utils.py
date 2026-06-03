from __future__ import annotations

from pathlib import Path


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
