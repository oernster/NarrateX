"""Port: cover extraction.

The UI needs cover bytes, but must not depend on infrastructure. This protocol
is the stable seam.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CoverExtractor(Protocol):
    def extract_cover_bytes(self, source_path: Path) -> bytes | None:
        """Return encoded cover bytes (PNG/JPG/etc.) if available."""
