"""One JSON object in one file: read it, write it, keep a damaged one aside.

Shared by the bookmark and preferences stores, which hold what the reader
cannot recreate. The rule both obey: absence is an answer (nothing saved yet);
damage is not. A file that will not parse is never read as empty and then
saved over. It is moved aside under a name no earlier kept copy holds, so the
reader's data is still on disk to be recovered by hand.
"""

from __future__ import annotations

import itertools
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DAMAGED_SUFFIX = ".damaged"

# The second kept copy is `<name>.damaged.2`; the first carries no number.
_FIRST_NUMBERED_COPY = 2


class DamagedDocumentError(ValueError):
    """The file exists and was read but does not hold a JSON object."""


def read_object(path: Path) -> dict | None:
    """The object stored at `path`; None when no file is there.

    An empty file holds nothing to lose, so it reads as absent. Raises
    `OSError` when the file cannot be read, since a read that fails may be
    transient and the file perfectly good. It raises `DamagedDocumentError` when what
    was read is not a JSON object.
    """

    if not path.exists():
        return None
    raw = path.read_bytes()
    if not raw.strip():
        return None
    try:
        # A byte that is not UTF-8 is damage too: UnicodeDecodeError is a
        # ValueError, as is every JSON syntax error.
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise DamagedDocumentError(str(path)) from exc
    if not isinstance(data, dict):
        raise DamagedDocumentError(str(path))
    return data


def keep_aside(path: Path) -> Path:
    """Move a damaged file to the first free kept-aside name and return it."""

    first = path.with_name(path.name + DAMAGED_SUFFIX)
    candidate = first
    numbers = itertools.count(_FIRST_NUMBERED_COPY)
    while candidate.exists():
        candidate = first.with_name(f"{first.name}.{next(numbers)}")
    path.rename(candidate)
    log.warning("Kept a damaged file aside: %s -> %s", path, candidate)
    return candidate


def object_for_update(path: Path) -> dict:
    """What to change before saving: the stored object; a fresh one when none.

    A damaged file is kept aside first, so the save that follows cannot
    destroy it. A file that cannot be read raises and nothing is saved.
    """

    try:
        return read_object(path) or {}
    except DamagedDocumentError:
        keep_aside(path)
        return {}


def write_object(path: Path, data: dict, *, sort_keys: bool = False) -> None:
    """Write through a temporary file and replace, so a crash leaves the old one."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=sort_keys), encoding="utf-8")
    tmp.replace(path)
