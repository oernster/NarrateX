"""Infrastructure: extract a book's front cover image.

This is intentionally best-effort.

Supported:
- EPUB: uses ebooklib's `get_cover()` when available.
- PDF: extracts the first page raster via PyMuPDF if available.

Returns raw encoded image bytes (PNG/JPG/etc.) suitable for Qt `QImage.fromData`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

_KINDLE_EXTS = {".mobi", ".azw", ".azw3", ".prc", ".kfx"}
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
_MAX_SIDECAR_BYTES = 12 * 1024 * 1024  # 12MB: avoid accidentally reading huge files


@dataclass(frozen=True, slots=True)
class CoverExtractor:
    def extract_cover_bytes(self, source_path: Path) -> bytes | None:
        """Return encoded cover bytes (PNG/JPG/etc.) if found.

        Strategy (best-effort):
        1) Prefer Calibre-style *sidecar* images next to the book file
           (e.g. cover.jpg in the same directory).
        2) Fall back to embedded extraction for formats we understand (EPUB/PDF).
        3) For Kindle formats, try converting to a temporary EPUB via Calibre
           `ebook-convert` and then extract from the converted EPUB.
        """

        log = logging.getLogger(self.__class__.__name__)
        try:
            abs_source = source_path.resolve()
        except Exception:
            abs_source = source_path

        log.debug("Cover: extract start source=%s", abs_source)

        # 1) Deterministic Calibre sidecar cover: exact cover.(jpg|jpeg|png|webp)
        # next to the selected book file.
        det_path = self._resolve_calibre_sidecar_cover_path(source_path)
        if det_path is not None:
            try:
                abs_det = det_path.resolve()
            except Exception:
                abs_det = det_path
            log.debug(
                "Cover: deterministic sidecar candidate=%s exists=%s",
                abs_det,
                det_path.exists(),
            )
            # For the deterministic Calibre cover path, prefer correctness over
            # the heuristic size-guard. Some real-world Calibre covers can be
            # large (high-res scans); skipping them leads to confusing fallbacks.
            det_bytes = self._safe_read_image_bytes(det_path, max_bytes=None)
            if det_bytes:
                log.info(
                    "Cover: using deterministic sidecar path=%s bytes=%s",
                    abs_det,
                    len(det_bytes),
                )
                log.debug(
                    "Cover: deterministic sidecar hit path=%s bytes=%s",
                    abs_det,
                    len(det_bytes),
                )
                self._maybe_dump_cover_bytes(
                    source_path=abs_source,
                    cover_bytes=det_bytes,
                    strategy="deterministic-sidecar",
                    cover_path=abs_det,
                )
                return det_bytes
            log.debug(
                "Cover: deterministic sidecar unreadable/empty path=%s; falling back",
                abs_det,
            )
        else:
            try:
                abs_parent = source_path.parent.resolve()
            except Exception:
                abs_parent = source_path.parent
            log.debug(
                "Cover: deterministic sidecar not found in folder=%s; falling back",
                abs_parent,
            )

        # 2) Generic sidecar fallback (heuristic)
        sidecar_bytes, sidecar_path = self._extract_sidecar_image_with_path(source_path)
        if sidecar_bytes:
            if sidecar_path is not None:
                try:
                    abs_sidecar = sidecar_path.resolve()
                except Exception:
                    abs_sidecar = sidecar_path
                log.info(
                    "Cover: using generic sidecar path=%s bytes=%s",
                    abs_sidecar,
                    len(sidecar_bytes),
                )
                self._maybe_dump_cover_bytes(
                    source_path=abs_source,
                    cover_bytes=sidecar_bytes,
                    strategy="generic-sidecar",
                    cover_path=abs_sidecar,
                )
            log.debug("Cover: generic sidecar hit bytes=%s", len(sidecar_bytes))
            return sidecar_bytes

        ext = source_path.suffix.lower()
        if ext == ".epub":
            data = self._extract_epub(source_path)
            if data:
                log.info("Cover: using epub extraction bytes=%s", len(data))
                self._maybe_dump_cover_bytes(
                    source_path=abs_source,
                    cover_bytes=data,
                    strategy="epub",
                    cover_path=None,
                )
            log.debug(
                "Cover: epub extraction %s",
                f"hit bytes={len(data)}" if data else "miss",
            )
            return data
        if ext == ".pdf":
            data = self._extract_pdf(source_path)
            if data:
                log.info("Cover: using pdf extraction bytes=%s", len(data))
                self._maybe_dump_cover_bytes(
                    source_path=abs_source,
                    cover_bytes=data,
                    strategy="pdf",
                    cover_path=None,
                )
            log.debug(
                "Cover: pdf extraction %s",
                f"hit bytes={len(data)}" if data else "miss",
            )
            return data
        if ext in _KINDLE_EXTS:
            data = self._extract_kindle_via_conversion(source_path)
            if data:
                log.info("Cover: using kindle conversion bytes=%s", len(data))
                self._maybe_dump_cover_bytes(
                    source_path=abs_source,
                    cover_bytes=data,
                    strategy="kindle-conversion",
                    cover_path=None,
                )
            log.debug(
                "Cover: kindle conversion %s",
                f"hit bytes={len(data)}" if data else "miss",
            )
            return data
        # TXT and unknown formats: no cover.
        return None

    def _maybe_dump_cover_bytes(
        self,
        *,
        source_path: Path,
        cover_bytes: bytes,
        strategy: str,
        cover_path: Path | None,
    ) -> None:
        """Optionally dump the extracted cover bytes to disk for debugging.

        Enabled by setting environment variable `NARRATEX_DUMP_COVER_BYTES=1`.

        By default, dumps to `%TEMP%/narratex-cover-dumps/` (Windows) / temp dir.
        Optionally override with `NARRATEX_COVER_DUMP_DIR`.
        """

        raw = os.getenv("NARRATEX_DUMP_COVER_BYTES", "").strip().lower()
        if raw not in ("1", "true", "yes", "on"):
            return

        try:
            import tempfile
            import time

            dump_dir_raw = os.getenv("NARRATEX_COVER_DUMP_DIR", "").strip()
            dump_dir = Path(dump_dir_raw) if dump_dir_raw else Path(tempfile.gettempdir()) / "narratex-cover-dumps"
            dump_dir.mkdir(parents=True, exist_ok=True)

            ts = int(time.time() * 1000)
            safe_stem = source_path.stem.replace(" ", "_")[:80]
            ext = None
            if cover_path is not None:
                ext = cover_path.suffix.lower().lstrip(".") or None
            if ext is None:
                ext = "bin"

            out_path = dump_dir / f"{safe_stem}__{strategy}__{ts}.{ext}"
            out_path.write_bytes(cover_bytes)

            log = logging.getLogger(self.__class__.__name__)
            log.info(
                "Cover: dumped bytes=%s strategy=%s dump_path=%s",
                len(cover_bytes),
                strategy,
                out_path,
            )
        except Exception:
            logging.getLogger(self.__class__.__name__).exception(
                "Cover: failed to dump cover bytes (strategy=%s)",
                strategy,
            )

    def _resolve_calibre_sidecar_cover_path(self, source_path: Path) -> Path | None:
        """Resolve an *exact* Calibre sidecar cover path.

        This intentionally implements the boring, deterministic CalibreBooks shape:

        - Look only in source_path.parent
        - Prefer exact cover.jpg
        - Then exact cover.jpeg
        - Then exact cover.png
        - Then exact cover.webp

        No recursion; no heuristics.
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

    @staticmethod
    def _safe_read_image_bytes(p: Path, *, max_bytes: int | None = _MAX_SIDECAR_BYTES) -> bytes | None:
        try:
            if not p.exists() or not p.is_file():
                return None
            if max_bytes is not None:
                try:
                    if p.stat().st_size > max_bytes:
                        return None
                except Exception:
                    # If we can't stat it, we also shouldn't try reading it.
                    return None
            return p.read_bytes()
        except Exception:
            return None

    def _extract_sidecar_image(self, source_path: Path) -> bytes | None:
        data, _ = self._extract_sidecar_image_with_path(source_path)
        return data

    def _extract_sidecar_image_with_path(
        self, source_path: Path
    ) -> tuple[bytes | None, Path | None]:
        """Look for Calibre-style sidecar cover images in the same folder.

        Many Calibre libraries store a `cover.jpg` adjacent to the ebook file
        (especially for Kindle formats), rather than embedding a cover inside the
        ebook.
        """

        folder = source_path.parent
        if not folder.exists():
            return None, None

        _safe_read = self._safe_read_image_bytes

        # 0) Exact cover.* should always win over any other heuristic.
        for name in ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp"):
            candidate = folder / name
            data = _safe_read(candidate)
            if data:
                return data, candidate

        # 1) Common Calibre/Windows names.
        preferred_stems = (
            "cover",
            "folder",
            "front",
        )
        for stem in preferred_stems:
            for ext in _IMAGE_EXTS:
                candidate = folder / f"{stem}{ext}"
                data = _safe_read(candidate)
                if data:
                    return data, candidate

        # 2) Heuristic scan: any image file with "cover"/"folder" in name.
        try:
            candidates: list[Path] = []
            for p in folder.iterdir():
                if not p.is_file():
                    continue
                if p.suffix.lower() not in _IMAGE_EXTS:
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
                data = _safe_read(p)
                if data:
                    return data, p
        except Exception:
            return None, None

        return None, None

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
                    # Support both single and double quotes, plus unquoted forms.
                    # We avoid full HTML parsing here by design.
                    matches = re.findall(
                        r"(?:xlink:href|src|href)\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))",
                        html,
                        flags=re.IGNORECASE,
                    )
                    if not matches:
                        continue

                    flat: list[str] = []
                    for m in matches:
                        if isinstance(m, tuple):
                            for part in m:
                                if part:
                                    flat.append(part)
                        elif m:
                            flat.append(m)
                    if not flat:
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
                    for cand in flat:
                        if _is_image_target(cand):
                            href = cand
                            break
                    if href is None:
                        href = flat[0]
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

    def _extract_kindle_via_conversion(self, path: Path) -> bytes | None:
        """Convert Kindle formats to a temporary EPUB and reuse EPUB extraction.

        This is best-effort and intentionally silent on failure; callers treat a
        None return as "no cover".
        """

        try:
            import subprocess
            import tempfile

            with tempfile.TemporaryDirectory(prefix="narratex-cover-") as tmp:
                out_path = Path(tmp) / f"{path.stem}.epub"
                cmd = ["ebook-convert", str(path), str(out_path)]
                try:
                    completed = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except FileNotFoundError:
                    return None

                if completed.returncode != 0 or not out_path.exists():
                    return None
                return self._extract_epub(out_path)
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

