"""Build the installer payload zip + manifest.

Input:
    dist-pyinstaller/NarrateX/  (PyInstaller onedir bundle)

Output:
    installer/payload/payload.zip
    installer/payload/manifest.json

The payload is deterministic:

- files are added in sorted order
- zip timestamps are normalized
"""

from __future__ import annotations

import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from installer.ops.cores import usable_cores
from installer.zip_writer import PackedMember, pack, write_zip
from voice_reader.version import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUNDLE_DIR = PROJECT_ROOT / "dist-pyinstaller" / "NarrateX"
PAYLOAD_DIR = PROJECT_ROOT / "installer" / "payload"
PAYLOAD_ZIP = PAYLOAD_DIR / "payload.zip"
MANIFEST_JSON = PAYLOAD_DIR / "manifest.json"

_MB = 1024 * 1024
# LZMA rather than deflate: measured on the trimmed bundle, 236 MB against
# deflate's 299 MB. On one thread it took 150 s against deflate's 20 s, so the
# members are compressed on every core (zip_writer). The installer reads it
# with zipfile, which handles both.
PAYLOAD_COMPRESSION = zipfile.ZIP_LZMA
# Hashing and compressing the whole bundle runs for minutes on a cold cache;
# without output it reads as a hang, so report at this fraction of the bytes.
_REPORT_FRACTION = 0.1


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if any(part in {"__pycache__"} for part in rel.parts):
                continue
            files.append(p)
    return sorted(files, key=lambda x: str(x.relative_to(root)).replace("\\", "/"))


def _packed_in_order(
    files: list[Path], names: list[str], workers: int
) -> Iterator[PackedMember]:
    """Every file packed, answered in the order given.

    On several cores the largest files start first: LZMA cannot split one
    file across cores, so the biggest set how long the whole takes and must
    not be left until last. Finished members wait, compressed, for their turn.
    """

    if workers <= 1:
        for path, name in zip(files, names):
            yield pack(path, name)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        largest_first = sorted(
            range(len(files)), key=lambda i: files[i].stat().st_size, reverse=True
        )
        futures = {i: pool.submit(pack, files[i], names[i]) for i in largest_first}
        for index in range(len(files)):
            yield futures.pop(index).result()


def write_payload(source: Path, zip_path: Path, *, workers: int) -> list[ManifestEntry]:
    """Compress `source` into `zip_path` on `workers` threads; answer the manifest."""

    files = _iter_files(source)
    names = [str(f.relative_to(source)).replace("\\", "/") for f in files]
    total_bytes = sum(f.stat().st_size for f in files)
    print(
        f"Building payload: hashing and compressing {len(files)} files "
        f"({total_bytes / _MB:.0f} MB) on {workers} thread(s)...",
        flush=True,
    )
    entries: list[ManifestEntry] = []
    progress = _Progress(total_bytes)

    def recorded() -> Iterator[PackedMember]:
        for member in _packed_in_order(files, names, workers):
            entries.append(
                ManifestEntry(path=member.name, size=member.size, sha256=member.sha256)
            )
            progress.add(member.size)
            yield member

    with zip_path.open("wb") as out:
        write_zip(out, recorded())
    return entries


class _Progress:
    """Prints every tenth of the bytes, once, however large one step is."""

    def __init__(self, total: int) -> None:
        self._total = total
        self._done = 0
        self._next = _REPORT_FRACTION

    def add(self, size: int) -> None:
        self._done += size
        if self._total <= 0 or self._done / self._total < self._next:
            return
        print(
            f"  {int(100 * self._done / self._total)}% ({self._done / _MB:.0f} MB)",
            flush=True,
        )
        # One large file can cross several marks at once; skip past every
        # mark already covered or the next file repeats it.
        while self._next <= self._done / self._total:
            self._next += _REPORT_FRACTION


def build_payload() -> None:
    if os.name != "nt":
        raise SystemExit("Payload build is intended for Windows builds")

    if not SOURCE_BUNDLE_DIR.exists():
        raise SystemExit(f"Source bundle not found: {SOURCE_BUNDLE_DIR}")

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    entries = write_payload(SOURCE_BUNDLE_DIR, PAYLOAD_ZIP, workers=usable_cores())
    print(f"Payload written: {PAYLOAD_ZIP}", flush=True)

    manifest = {
        "installer_version": __version__,
        "bundle_root": "NarrateX",
        "entries": [asdict(e) for e in entries],
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build_payload()
