from __future__ import annotations

from pathlib import Path


def extract_kindle_via_conversion(
    path: Path,
    *,
    extract_epub_cover,
) -> bytes | None:
    """Convert Kindle formats to a temporary EPUB and reuse EPUB extraction."""

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
            return extract_epub_cover(out_path)
    except Exception:
        return None
