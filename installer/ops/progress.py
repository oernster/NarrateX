"""How an install reports its progress.

An install is one 0 to 100 run made of phases of very unequal length. The
percentages live here rather than at the call sites so the phases stay in order
and cannot drift apart, and so a reader can see the whole shape of the run in
one place.
"""

from __future__ import annotations

# Extraction owns the opening band because it is by far the longest phase: it
# writes the entire application bundle to disk. The steps after it are quick
# and each reports a single point.
EXTRACT_START_PCT = 10
EXTRACT_END_PCT = 45
REGISTER_PCT = 75
SHORTCUTS_PCT = 90
COMPLETE_PCT = 100

EXTRACT_MESSAGE = "Extracting payload..."


def report(progress, *, pct: int | None, message: str) -> None:  # noqa: ANN001
    """Send one progress report, if anyone is listening.

    A report without a percentage is a message only, which leaves the bar where
    it is. The UI reads the two forms apart, so the shape is part of the
    contract rather than an implementation detail.
    """

    if not progress:
        return
    if pct is None:
        progress(message)
    else:
        progress({"pct": int(pct), "message": message})
