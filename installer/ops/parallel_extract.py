"""Unpacking the payload's files on every core the machine offers.

LZMA is slow to decode on one core. Its decoder releases the GIL, so the
members are shared out by size among threads, each reading through its own
handle on the archive; a machine with one core extracts them in turn on the
calling thread instead, with no pool at all.

Progress stays a single rising line however many threads feed it: every
chunk is counted under one lock and reported there when the percentage moves.
A cancel stops every thread at its next chunk; so does a failure on any one.
"""

from __future__ import annotations

import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from installer.ops.errors import InstallerOperationError
from installer.ops.progress import (
    EXTRACT_END_PCT,
    EXTRACT_MESSAGE,
    EXTRACT_START_PCT,
    report,
)

# Streaming granularity for extraction. The bundle carries individual members
# of hundreds of megabytes (models, Qt libraries); reporting only between
# members held the bar still for the whole of each one; it also gave Cancel
# nothing to observe while one was in flight.
CHUNK_BYTES = 4 * 1024 * 1024


class _Stopped(Exception):
    """Another thread failed or was cancelled; this one stands down."""


class _Tally:
    """Bytes written across every thread, reported as one rising percentage."""

    def __init__(self, total: int, progress) -> None:  # noqa: ANN001
        self._lock = threading.Lock()
        self._total = total
        self._done = 0
        self._last = EXTRACT_START_PCT
        self._progress = progress
        self.stop = threading.Event()

    def add(self, size: int) -> None:
        with self._lock:
            self._done += size
            if self._total <= 0:
                return
            span = EXTRACT_END_PCT - EXTRACT_START_PCT
            pct = EXTRACT_START_PCT + int(span * self._done / self._total)
            if pct != self._last:
                report(self._progress, pct=pct, message=EXTRACT_MESSAGE)
                self._last = pct


def split_by_size(
    members: list[zipfile.ZipInfo], count: int
) -> list[list[zipfile.ZipInfo]]:
    """At most `count` shares of near equal bytes; always at least one.

    Largest first, each to the lightest share so far: a big library cannot be
    split across threads, so it must not land last on a busy one.
    """

    shares: list[list[zipfile.ZipInfo]] = [
        [] for _ in range(max(1, min(count, len(members))))
    ]
    loads = [0] * len(shares)
    for member in sorted(members, key=lambda m: m.file_size, reverse=True):
        lightest = loads.index(min(loads))
        shares[lightest].append(member)
        loads[lightest] += member.file_size
    return shares


def _guard(tally: _Tally, cancel_event) -> None:  # noqa: ANN001
    if tally.stop.is_set():
        raise _Stopped
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise InstallerOperationError("Cancelled")


def _extract_share(
    source: Path,
    share: list[zipfile.ZipInfo],
    targets: dict[str, Path],
    tally: _Tally,
    cancel_event,  # noqa: ANN001
) -> None:
    try:
        with zipfile.ZipFile(source, "r") as zf:
            for member in share:
                _guard(tally, cancel_event)
                with zf.open(member) as src, targets[member.filename].open("wb") as dst:
                    while chunk := src.read(CHUNK_BYTES):
                        dst.write(chunk)
                        tally.add(len(chunk))
                        _guard(tally, cancel_event)
    except _Stopped:
        raise
    except BaseException:
        tally.stop.set()
        raise


def extract_members(
    source: Path,
    members: list[zipfile.ZipInfo],
    targets: dict[str, Path],
    *,
    workers: int,
    progress=None,  # noqa: ANN001
    cancel_event=None,  # noqa: ANN001
) -> None:
    """Write each member to its target on up to `workers` threads.

    Every target's folder must exist already: threads only write files.
    """

    tally = _Tally(sum(m.file_size for m in members), progress)
    shares = split_by_size(members, workers)
    if len(shares) == 1:
        _extract_share(source, shares[0], targets, tally, cancel_event)
        return
    with ThreadPoolExecutor(max_workers=len(shares)) as pool:
        futures = [
            pool.submit(_extract_share, source, share, targets, tally, cancel_event)
            for share in shares
        ]
    failures = [
        f.exception()
        for f in futures
        if f.exception() is not None and not isinstance(f.exception(), _Stopped)
    ]
    if failures:
        raise failures[0]
