"""Book conversion using Calibre `ebook-convert`.

Kindle formats are converted to EPUB for parsing.

**Calibre is given an environment that is not ours.** `ebook-convert` is itself a
Qt application; a packaged NarrateX tells Qt where ITS plugins live through
the environment. A child inheriting that reads our plugins with Calibre's own Qt,
which cannot load them: the conversion then dies part way through with a Qt
platform-plugin error instead of producing a book.

Measured on 2026-09-20 with the installed build's plugin directory: the same
file, the same command, converts in full with a clean environment and dies at
Calibre's cover step with `QT_PLUGIN_PATH` set to ours.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from voice_reader.domain.shelf import formats
from voice_reader.shared.errors import BookConversionError

# Variables that tell a Qt program where to find its own parts. Every one of
# them is about NarrateX and none of them is true for another Qt program, so
# they are dropped rather than corrected: Calibre knows where Calibre lives.
QT_ENVIRONMENT_PREFIXES: tuple[str, ...] = (
    "QT_",
    "QTDIR",
    "QML_",
    "QML2_",
    "PYSIDE",
)


def child_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """This process's environment with everything Qt-specific to us removed."""

    source = os.environ if environ is None else environ
    return {
        name: value
        for name, value in source.items()
        if not name.upper().startswith(QT_ENVIRONMENT_PREFIXES)
    }


@dataclass(frozen=True, slots=True)
class CalibreConverter:
    temp_books_dir: Path
    ebook_convert_exe: str = "ebook-convert"
    # The runner is injected so a test can read the environment a conversion
    # would be given without paying 2.3 seconds for a real conversion.
    runner: Callable[..., subprocess.CompletedProcess] = field(default=subprocess.run)

    def convert_to_epub_if_needed(self, source_path: Path) -> Path:
        ext = source_path.suffix.lower()
        if ext in formats.NATIVE:
            return source_path
        if ext not in formats.KINDLE:
            raise BookConversionError(f"Unsupported book format: {ext}")

        out_dir = self.temp_books_dir / "epub"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{source_path.stem}.epub"

        cmd = [self.ebook_convert_exe, str(source_path), str(out_path)]
        try:
            completed = self.runner(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=child_environment(),
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
