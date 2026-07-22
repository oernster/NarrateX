"""Getting the application bundle onto disk.

An install never writes into the target directory directly. The payload is
unpacked to a staging area first and only swapped into place once it is whole,
so a failure part way through leaves the existing installation untouched.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from installer.ops.errors import InstallerOperationError
from installer.ops.payload import payload_zip_path
from installer.ops.progress import (
    CLEANUP_END_PCT,
    CLEANUP_MESSAGE,
    CLEANUP_START_PCT,
    EXTRACT_END_PCT,
    EXTRACT_MESSAGE,
    EXTRACT_START_PCT,
    report,
)

logger = logging.getLogger("installer.install")

# Streaming granularity for extraction. The bundle carries individual members
# of hundreds of megabytes (models, Qt libraries); reporting only between
# members held the bar still for the whole of each one, and gave Cancel
# nothing to observe while one was in flight.
_CHUNK_BYTES = 4 * 1024 * 1024


def check_cancel(cancel_event) -> None:  # noqa: ANN001
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise InstallerOperationError("Cancelled")


def installer_staging_root() -> Path:
    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "NarrateXInstaller" / "staging"


def extract_payload_to(
    staging_dir: Path, *, progress=None, cancel_event=None, zip_path: Path | None = None
) -> None:  # noqa: ANN001
    """Unpack the payload, reporting progress as it goes.

    Extraction is the long part of an install and it used to run as a single
    blocking `extractall`, so the bar sat at its opening value until the whole
    bundle had landed. Streaming each member in chunks reports real progress
    even through the largest single files and gives Cancel a place to take
    effect every few megabytes rather than only between members.

    `zip_path` defaults to the bundled payload. It is injectable so the
    reporting can be exercised against a small archive rather than only against
    a real build.
    """

    staging_dir.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel_event)
    report(progress, pct=EXTRACT_START_PCT, message=EXTRACT_MESSAGE)
    logger.info("Extracting payload to %s", staging_dir)

    source = payload_zip_path() if zip_path is None else zip_path
    with zipfile.ZipFile(source, "r") as zf:
        members = zf.infolist()
        # Uncompressed size tracks elapsed work far better than a file count,
        # because a bundle is a few large libraries among many small files.
        total_bytes = sum(m.file_size for m in members)
        span = EXTRACT_END_PCT - EXTRACT_START_PCT
        extracted = 0
        last_pct = EXTRACT_START_PCT

        for member in members:
            check_cancel(cancel_event)
            target = _member_target(staging_dir, member)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    dst.write(chunk)
                    extracted += len(chunk)

                    if total_bytes > 0:
                        pct = EXTRACT_START_PCT + int(span * extracted / total_bytes)
                        if pct != last_pct:
                            report(progress, pct=pct, message=EXTRACT_MESSAGE)
                            last_pct = pct
                    check_cancel(cancel_event)

    check_cancel(cancel_event)

    exe = staging_dir / "NarrateX.exe"
    internal = staging_dir / "_internal"
    if not exe.exists() or not internal.exists():
        raise InstallerOperationError("Payload is missing NarrateX.exe or _internal/")


def _member_target(staging_dir: Path, member: zipfile.ZipInfo) -> Path:
    """Resolve a member's destination, refusing paths that escape staging."""

    target = (staging_dir / member.filename).resolve()
    if not target.is_relative_to(staging_dir.resolve()):
        raise InstallerOperationError(
            f"Payload entry escapes the staging directory: {member.filename}"
        )
    return target


def remove_tree_reporting(root: Path, *, progress=None) -> None:  # noqa: ANN001
    """Delete a tree file by file, reporting through the cleanup band.

    A previous install is tens of thousands of files and one silent rmtree
    parks the bar for its whole duration. Deletion cost is per file, so the
    report counts files rather than bytes. Failures are ignored exactly as
    the rmtree they replace ignored them; the closing rmtree sweeps up the
    directories and any stragglers.
    """

    if not root.exists():
        return

    files = [p for p in root.rglob("*") if p.is_file()]
    total = len(files)
    span = CLEANUP_END_PCT - CLEANUP_START_PCT
    report(progress, pct=CLEANUP_START_PCT, message=CLEANUP_MESSAGE)
    last_pct = CLEANUP_START_PCT
    for index, path in enumerate(files, start=1):
        try:
            path.unlink()
        except Exception:
            pass
        if total > 0:
            pct = CLEANUP_START_PCT + int(span * index / total)
            if pct != last_pct:
                report(progress, pct=pct, message=CLEANUP_MESSAGE)
                last_pct = pct
    shutil.rmtree(root, ignore_errors=True)


def swap_in_bundle(
    staging_dir: Path, target_dir: Path, *, progress=None
) -> None:  # noqa: ANN001
    """Replace target_dir with staging_dir.

    Uses a same-volume rename when possible; falls back to copytree when
    installing across different volumes.
    """

    target_dir = target_dir.resolve()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Swapping bundle into %s (staging=%s)", target_dir, staging_dir)

    backup_dir: Path | None = None
    if target_dir.exists():
        backup_dir = target_dir.with_name(
            target_dir.name + f".old.{uuid.uuid4().hex[:8]}"
        )
        try:
            target_dir.rename(backup_dir)
        except Exception as exc:
            raise InstallerOperationError(
                f"Unable to replace existing install at {target_dir}"
            ) from exc

    try:
        try:
            staging_dir.rename(target_dir)
        except OSError:
            # Likely cross-volume move. Copy instead.
            shutil.copytree(staging_dir, target_dir, dirs_exist_ok=False)
            shutil.rmtree(staging_dir, ignore_errors=True)
    except Exception:
        # Rollback.
        if backup_dir and backup_dir.exists() and not target_dir.exists():
            try:
                backup_dir.rename(target_dir)
            except Exception:
                pass
        raise
    finally:
        if backup_dir and backup_dir.exists():
            remove_tree_reporting(backup_dir, progress=progress)
