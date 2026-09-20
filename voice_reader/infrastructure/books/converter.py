"""Book conversion using Calibre `ebook-convert`.

Kindle formats are converted to EPUB for parsing. How Calibre is invoked,
plus the two things that invocation has to get right, lives in `ebook_convert`
beside this module, because the cover reader calls it too.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.infrastructure.books.ebook_convert import (
    EBOOK_CONVERT,
    Runner,
    run_ebook_convert,
)
from voice_reader.shared.errors import BookConversionError


@dataclass(frozen=True, slots=True)
class CalibreConverter:
    temp_books_dir: Path
    ebook_convert_exe: str = EBOOK_CONVERT
    # The runner is injected so a test can read the environment a conversion
    # would be given without paying 2.3 seconds for a real conversion.
    runner: Runner = field(default=subprocess.run)

    def convert_to_epub_if_needed(self, source_path: Path) -> Path:
        ext = source_path.suffix.lower()
        if ext in formats.NATIVE:
            return source_path
        if ext not in formats.KINDLE:
            raise BookConversionError(f"Unsupported book format: {ext}")

        out_dir = self.temp_books_dir / "epub"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{source_path.stem}.epub"

        try:
            completed = run_ebook_convert(
                source_path,
                out_path,
                exe=self.ebook_convert_exe,
                runner=self.runner,
            )
        except FileNotFoundError as exc:
            raise BookConversionError(
                "Calibre 'ebook-convert' not found on PATH"
            ) from exc

        if completed.returncode != 0:
            raise BookConversionError(
                f"ebook-convert failed: {completed.stderr.strip() or completed.stdout}"
            )

        if not out_path.exists():
            raise BookConversionError("Conversion did not produce an output EPUB")
        return out_path
