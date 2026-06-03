from __future__ import annotations

from pathlib import Path


def extract_pdf_cover(path: Path) -> bytes | None:
    """Extract a cover image for PDFs by rasterizing the first page (best-effort)."""

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
