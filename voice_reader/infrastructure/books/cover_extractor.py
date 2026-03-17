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

from voice_reader.infrastructure.books.cover.epub import extract_epub_cover
from voice_reader.infrastructure.books.cover.kindle import extract_kindle_via_conversion
from voice_reader.infrastructure.books.cover.pdf import extract_pdf_cover
from voice_reader.infrastructure.books.cover.sidecar import (
    extract_sidecar_image_with_path,
    resolve_calibre_sidecar_cover_path,
)
from voice_reader.infrastructure.books.cover._io_utils import safe_read_image_bytes

_KINDLE_EXTS = {".mobi", ".azw", ".azw3", ".prc", ".kfx"}
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
        det_path = resolve_calibre_sidecar_cover_path(source_path)
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
            det_bytes = safe_read_image_bytes(det_path, max_bytes=None)
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
        sidecar_bytes, sidecar_path = extract_sidecar_image_with_path(
            source_path, max_bytes=_MAX_SIDECAR_BYTES
        )
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
            data = extract_epub_cover(source_path)
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
            data = extract_pdf_cover(source_path)
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
            data = extract_kindle_via_conversion(
                source_path, extract_epub_cover=extract_epub_cover
            )
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
            dump_dir = (
                Path(dump_dir_raw)
                if dump_dir_raw
                else Path(tempfile.gettempdir()) / "narratex-cover-dumps"
            )
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

    # Implementation is split into strategy modules under
    # voice_reader.infrastructure.books.cover.*
