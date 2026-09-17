"""How an install reports its progress.

An install is one 0 to 100 run made of phases of very unequal length. The
percentages live here rather than at the call sites so the phases stay in order
and cannot drift apart; a reader can see the whole shape of the run in
one place.
"""

from __future__ import annotations

# Three phases dominate an install and each owns a band reported
# continuously: extraction writes the application bundle to disk, cleanup
# deletes the previous version file by file; the uninstaller copy
# duplicates the whole setup executable (which embeds that same bundle) into
# the install directory. The steps between and after are quick and each
# reports a single point.
EXTRACT_START_PCT = 10
EXTRACT_END_PCT = 40
CLEANUP_START_PCT = 40
CLEANUP_END_PCT = 50
COPY_UNINSTALLER_START_PCT = 50
COPY_UNINSTALLER_END_PCT = 70
REGISTER_PCT = 75
SHORTCUTS_PCT = 90
COMPLETE_PCT = 100

# A repair checks every installed file against the manifest and rewrites the
# ones that differ. Both hashing and rewriting cost time in proportion to a
# file's size, so the verification band advances by bytes rather than by file
# count; the shortcut and registry steps that follow are quick single points.
REPAIR_VERIFY_START_PCT = 0
REPAIR_VERIFY_END_PCT = 90
REPAIR_SHORTCUTS_PCT = 93
REPAIR_REGISTER_PCT = 96

# An uninstall is a handful of steps, each reported as a single point when it
# begins. Removing the user data takes the widest band because it deletes the
# narration cache; that ordering is read from what the step deletes, not timed.
UNINSTALL_READ_PCT = 5
UNINSTALL_SHORTCUTS_PCT = 15
UNINSTALL_REGISTRY_PCT = 25
UNINSTALL_USER_DATA_PCT = 35
UNINSTALL_SCHEDULE_PCT = 90

EXTRACT_MESSAGE = "Extracting payload..."
CLEANUP_MESSAGE = "Removing the previous version..."
COPY_UNINSTALLER_MESSAGE = "Copying uninstaller..."


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
