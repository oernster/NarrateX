"""Infrastructure: extract a book's front cover image.

This is intentionally best-effort.

Supported:
- EPUB: uses ebooklib's `get_cover()` when available.
- PDF: extracts the first page raster via PyMuPDF if available.

Returns raw encoded image bytes (PNG/JPG/etc.) suitable for Qt `QImage.fromData`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CoverExtractor:
    def extract_cover_bytes(self, source_path: Path) -> bytes | None:
        ext = source_path.suffix.lower()
        if ext == ".epub":
            return self._extract_epub(source_path)
        if ext == ".pdf":
            return self._extract_pdf(source_path)
        # TXT and unknown formats: no cover.
        return None

    def _extract_epub(self, path: Path) -> bytes | None:
        # NOTE:
        # We intentionally use a ZIP-level parser rather than ebooklib metadata
        # helpers. Some real-world EPUBs include cover images that ebooklib
        # doesn't surface as ITEM_IMAGE, which results in “No cover” even though
        # the file contains one.
        try:
            import re
            import zipfile

            with zipfile.ZipFile(path) as z:
                names = z.namelist()

                def _read(name: str) -> bytes | None:
                    try:
                        return z.read(name)
                    except Exception:
                        return None

                def _normalize(path_str: str) -> str:
                    parts: list[str] = []
                    for part in path_str.replace("\\", "/").split("/"):
                        if part in ("", "."):
                            continue
                        if part == "..":
                            if parts:
                                parts.pop()
                            continue
                        parts.append(part)
                    return "/".join(parts)

                # 1) Find a cover document (cover.xhtml/html).
                cover_docs = [
                    n
                    for n in names
                    if n.lower().endswith(("cover.xhtml", "cover.html", "cover.htm"))
                ]
                if not cover_docs:
                    # Fallback: any xhtml/html with "cover" in the name.
                    cover_docs = [
                        n
                        for n in names
                        if "cover" in n.lower()
                        and n.lower().endswith((".xhtml", ".html", ".htm"))
                    ]

                for doc_name in cover_docs:
                    raw = _read(doc_name)
                    if not raw:
                        continue
                    html = raw.decode("utf-8", errors="ignore")

                    # Look for image references inside the cover doc.
                    # IMPORTANT: cover.xhtml often includes a CSS <link href=...>
                    # before the actual cover <image xlink:href=...>, so we must
                    # prefer *image-like* targets.
                    matches = re.findall(
                        r"(?:xlink:href|src|href)\s*=\s*\"([^\"]+)\"",
                        html,
                        flags=re.IGNORECASE,
                    )
                    if not matches:
                        continue

                    def _is_image_target(s: str) -> bool:
                        s_l = s.lower().split("?", 1)[0].split("#", 1)[0]
                        return s_l.endswith((
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".webp",
                            ".bmp",
                            ".svg",
                        ))

                    # Prefer explicit image refs, else fall back to first match.
                    href = None
                    for cand in matches:
                        if _is_image_target(cand):
                            href = cand
                            break
                    if href is None:
                        href = matches[0]
                    href = href.split("#", 1)[0]
                    if not href:
                        continue

                    base_dir = "/".join(doc_name.split("/")[:-1])
                    combined = f"{base_dir}/{href}" if base_dir else href
                    candidate = _normalize(combined)

                    # Try direct hit.
                    data = _read(candidate)
                    if data:
                        return data

                    # Try suffix match (zip entries may include a top-level folder).
                    for n in names:
                        if _normalize(n).endswith(candidate):
                            data2 = _read(n)
                            if data2:
                                return data2

                # 2) Heuristic: choose the first image-like asset.
                image_names = [
                    n
                    for n in names
                    if n.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                ]
                image_names.sort(key=lambda n: ("cover" not in n.lower(), n.lower()))
                for n in image_names:
                    data = _read(n)
                    if data:
                        return data
                return None
        except Exception:
            return None

    def _extract_pdf(self, path: Path) -> bytes | None:
        # Render first page to PNG bytes.
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(path))
            if doc.page_count <= 0:
                return None
            page = doc.load_page(0)
            # Slight upscaling for a nicer thumbnail.
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return pix.tobytes("png")
        except Exception:
            return None

