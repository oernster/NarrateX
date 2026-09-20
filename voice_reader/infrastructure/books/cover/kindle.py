"""A Kindle cover recovered by converting the book, as a last resort.

The shelf never comes here: it reads a Kindle cover straight out of the file's
own header in about a millisecond. This is the reader's path, for the one book
already being opened, where the conversion is being paid for anyway.

The conversion runs through `ebook_convert`, which is what keeps Calibre out of
our Qt environment and its console window off the screen.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from voice_reader.infrastructure.books.ebook_convert import run_ebook_convert


def extract_kindle_via_conversion(
    path: Path,
    *,
    extract_epub_cover,
) -> bytes | None:
    """Convert Kindle formats to a temporary EPUB and reuse EPUB extraction."""

    try:
        with tempfile.TemporaryDirectory(prefix="narratex-cover-") as tmp:
            out_path = Path(tmp) / f"{path.stem}.epub"
            try:
                completed = run_ebook_convert(path, out_path)
            except FileNotFoundError:
                return None

            if completed.returncode != 0 or not out_path.exists():
                return None
            return extract_epub_cover(out_path)
    except Exception:
        return None
