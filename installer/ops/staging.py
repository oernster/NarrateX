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
    EXTRACT_END_PCT,
    EXTRACT_MESSAGE,
    EXTRACT_START_PCT,
    report,
)

logger = logging.getLogger("installer.install")


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
    bundle had landed. Going member by member reports real progress and gives
    Cancel somewhere to take effect, which a single call also denied it.

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
            zf.extract(member, staging_dir)
            extracted += member.file_size

            if total_bytes <= 0:
                continue
            pct = EXTRACT_START_PCT + int(span * extracted / total_bytes)
            if pct != last_pct:
                report(progress, pct=pct, message=EXTRACT_MESSAGE)
                last_pct = pct

    check_cancel(cancel_event)

    exe = staging_dir / "NarrateX.exe"
    internal = staging_dir / "_internal"
    if not exe.exists() or not internal.exists():
        raise InstallerOperationError("Payload is missing NarrateX.exe or _internal/")


def swap_in_bundle(staging_dir: Path, target_dir: Path) -> None:
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
            shutil.rmtree(backup_dir, ignore_errors=True)
