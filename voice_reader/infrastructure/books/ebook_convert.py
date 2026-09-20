"""How NarrateX calls Calibre: one place, because two places drifted.

Both the book conversion and the reader's cover extraction run
`ebook-convert`; both need the same two things that are easy to forget.

**Calibre is given an environment that is not ours.** `ebook-convert` is itself a
Qt program; a packaged NarrateX tells Qt where ITS plugins live through the
environment. A child inheriting that reads our plugins with Calibre's own Qt,
which cannot load them: the conversion then dies part way through with a Qt
platform-plugin error instead of producing a book. Measured on 2026-09-20
against the installed build's plugin directory: the same file and the same
command convert in full with a clean environment and crash outright with
`QT_PLUGIN_PATH` set to ours.

**No console window.** Windows gives a console program a console of its own,
which appears and vanishes as a black flash over the reader's screen every time
a Kindle book is opened.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

EBOOK_CONVERT = "ebook-convert"

# Variables that tell a Qt program where to find its own parts. Every one of
# them is about NarrateX and none of them is true for another Qt program, so
# they are dropped rather than corrected: Calibre knows where Calibre lives.
QT_ENVIRONMENT_PREFIXES: tuple[str, ...] = (
    "QT_",
    "QTDIR",
    "QML_",
    "QML2_",
    "PYSIDE",
)

# Absent on every platform but Windows, so it is read off the module rather
# than written as its number; zero is what the other platforms want.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

Runner = Callable[..., subprocess.CompletedProcess]


def child_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """This process's environment with everything Qt-specific to us removed."""

    source = os.environ if environ is None else environ
    return {
        name: value
        for name, value in source.items()
        if not name.upper().startswith(QT_ENVIRONMENT_PREFIXES)
    }


def run_ebook_convert(
    source: Path,
    destination: Path,
    *,
    exe: str = EBOOK_CONVERT,
    runner: Runner | None = None,
) -> subprocess.CompletedProcess:
    """Convert one book, saying nothing about what failure means.

    The caller decides that: a conversion that fails is an error to the reader
    opening a book and merely no picture to the one drawing a cover.

    The default runner is read when the call is made rather than when this
    module is imported, so `subprocess.run` patched by a test is still the one
    that runs. A default argument would have captured the original and left
    such a test silently driving the real Calibre.
    """

    run = subprocess.run if runner is None else runner
    return run(
        [exe, str(source), str(destination)],
        capture_output=True,
        text=True,
        check=False,
        env=child_environment(),
        creationflags=NO_WINDOW,
    )
