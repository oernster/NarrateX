from __future__ import annotations

from pathlib import Path

from voice_reader.infrastructure.books.cover._io_utils import safe_read_image_bytes

IMAGE_EXTS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def resolve_calibre_sidecar_cover_path(source_path: Path) -> Path | None:
    """Resolve an *exact* Calibre sidecar cover path.

    Deterministic CalibreBooks shape:
    - Look only in source_path.parent
    - Prefer exact cover.jpg
    - Then exact cover.jpeg
    - Then exact cover.png
    - Then exact cover.webp
    """

    folder = source_path.parent
    if not folder.exists():
        return None

    for name in ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp"):
        candidate = folder / name
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except Exception:
            # Permission errors or other IO surprises should not kill cover loading.
            continue
    return None


def extract_sidecar_image_with_path(
    source_path: Path,
    *,
    max_bytes: int,
) -> tuple[bytes | None, Path | None]:
    """Best-effort sidecar cover extraction from the book's containing folder."""

    folder = source_path.parent
    if not folder.exists():
        return None, None

    # 0) Exact cover.* should always win over any other heuristic.
    for name in ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp"):
        candidate = folder / name
        data = safe_read_image_bytes(candidate, max_bytes=max_bytes)
        if data:
            return data, candidate

    # 1) Common Calibre/Windows stems.
    for stem in ("cover", "folder", "front"):
        for ext in IMAGE_EXTS:
            candidate = folder / f"{stem}{ext}"
            data = safe_read_image_bytes(candidate, max_bytes=max_bytes)
            if data:
                return data, candidate

    # 2) Heuristic scan: any image file with "cover"/"folder" in name.
    try:
        candidates: list[Path] = []
        for p in folder.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in IMAGE_EXTS:
                continue
            name = p.name.lower()
            if "cover" in name or "folder" in name:
                candidates.append(p)

        def _rank(p: Path) -> tuple[int, str]:
            n = p.name.lower()
            if n.startswith("cover"):
                return (0, n)
            if "cover" in n:
                return (1, n)
            if n.startswith("folder"):
                return (2, n)
            return (3, n)

        for p in sorted(candidates, key=_rank):
            data = safe_read_image_bytes(p, max_bytes=max_bytes)
            if data:
                return data, p
    except Exception:
        return None, None

    return None, None
