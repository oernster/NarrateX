"""Startup logging and stdio, bound to the running process.

`startup_diagnostics` holds the same logic in pure form: it takes the argv, the
streams and the opener as arguments so it can be tested without touching the
process. This module is the thin layer that binds those arguments to the real
`sys` and the real `open`, which is the part an entrypoint actually wants.

Keeping the two apart is deliberate. Startup failures have to be visible in a
windowed build, where there is no console to print to, so this code runs before
anything else and cannot itself be allowed to fail obscurely.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from voice_reader.shared.startup_diagnostics import (
    append_startup_log as _append_startup_log,
    ensure_stdio as _ensure_stdio,
    program_base_dir as _program_base_dir,
)


def program_base_dir(*, argv: list[str] | None = None) -> Path:
    """The directory the program was launched from."""

    source = sys.argv if argv is None else argv
    return _program_base_dir(argv0=(source[0] if source else ""), cwd=Path.cwd)


def append_startup_log(
    filename: str,
    text: str,
    *,
    base_dir: Path | None = None,
    open_fn: Callable[..., object] | None = None,
) -> None:
    """Append a line to a log file beside the program."""

    _append_startup_log(
        base_dir=program_base_dir() if base_dir is None else base_dir,
        filename=filename,
        text=text,
        # Resolved on each call rather than bound as a default, so a test that
        # replaces the builtin still reaches this.
        open_fn=open if open_fn is None else open_fn,
    )


def ensure_stdio(
    *,
    base_dir: Path | None = None,
    open_fn: Callable[..., object] | None = None,
) -> None:
    """Give the process usable stdout and stderr, redirecting them if not.

    A windowed build starts with no console attached, so writes to the real
    streams can fail outright. Replacing them keeps every later diagnostic
    somewhere a reader can find it.
    """

    out, err = _ensure_stdio(
        base_dir=program_base_dir() if base_dir is None else base_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        open_fn=open if open_fn is None else open_fn,
    )
    sys.stdout = out
    sys.stderr = err
