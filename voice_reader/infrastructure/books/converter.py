"""Book conversion using Calibre `ebook-convert`.

Kindle formats are converted to EPUB for parsing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from voice_reader.shared.errors import BookConversionError

_KINDLE_EXTS = {".mobi", ".azw", ".azw3", ".prc", ".kfx"}


@dataclass(frozen=True, slots=True)
class CalibreConverter:
    temp_books_dir: Path
    ebook_convert_exe: str = "ebook-convert"

    def convert_to_epub_if_needed(self, source_path: Path) -> Path:
        ext = source_path.suffix.lower()
        if ext in {".epub", ".pdf", ".txt"}:
            return source_path
        if ext not in _KINDLE_EXTS:
            raise BookConversionError(f"Unsupported book format: {ext}")

        out_dir = self.temp_books_dir / "epub"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{source_path.stem}.epub"

        cmd = [self.ebook_convert_exe, str(source_path), str(out_path)]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
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
