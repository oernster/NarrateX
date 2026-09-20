"""The downscaled cover art the grid draws (FR-BS-034, FR-BS-035).

One file per work, named by a hash of its token, so a title holding a colon or
a slash never has to be spelled into a filename. Everything here is derived: a
cache emptied by hand or by the reader comes back on the next scan; nothing
the reader stated lives in it.

Writes land through a temporary file and a replace, so a run that ends mid-write
leaves the previous thumbnail rather than half of a new one.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

THUMBNAIL_SUFFIX = ".thumb"

# Measured on 2026-09-19: a 320x480 cover at quality 82 averages 29 KB, so a
# thumbnail far past this is not a thumbnail.
_MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileThumbnailStore:
    """Holds one image per work, under the application's cache directory."""

    directory: Path

    def _path_for(self, token: str) -> Path:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{digest}{THUMBNAIL_SUFFIX}"

    def has(self, token: str) -> bool:
        return self._path_for(token).is_file()

    def get(self, token: str) -> bytes | None:
        path = self._path_for(token)
        try:
            if path.stat().st_size > _MAX_THUMBNAIL_BYTES:
                return None
            return path.read_bytes()
        except OSError:
            return None

    def put(self, token: str, image: bytes) -> None:
        """Write one thumbnail, atomically.

        A caller with nothing to store is storing nothing rather than an empty
        file, since an empty file reads back as a cover that failed to draw.
        """

        if not image:
            return
        final = self._path_for(token)
        temporary = final.with_suffix(final.suffix + ".part")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(image)
            os.replace(temporary, final)
        except OSError:
            # A cache that cannot be written is a slower shelf, never a
            # stopped one. A part file left behind is swept by `clear` and
            # overwritten by the next successful write of the same token.
            return

    def forget(self, token: str) -> None:
        self._path_for(token).unlink(missing_ok=True)

    def clear(self) -> None:
        """Empty the cache. Everything in it is derived."""

        for path in sorted(self.directory.glob(f"*{THUMBNAIL_SUFFIX}*")):
            path.unlink(missing_ok=True)
