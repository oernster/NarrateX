"""Startup diagnostics helpers.

The entrypoint (`app.py`) needs a few best-effort utilities that:
- work in windowed builds (stdout/stderr may start as None)
- write logs near the executable
- support a fast "preflight" mode for installer/CI

These helpers are dependency-injected (argv/open/import hooks) so they stay easy
to test without patching globals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, ContextManager, IO, Any


def preflight_imports(
    *,
    heavy: bool,
    import_module: Callable[[str], object],
    dist_version: Callable[[str], str],
) -> tuple[int, str]:
    """Return (rc, report).

    rc is 0 when all imports succeed, otherwise 2.
    """

    # Keep this list small and stable. The goal is to validate the packaged
    # runtime has the critical wheels available, not to fully initialize them.
    modules = [
        # Basic stdlib/bootstrap sanity.
        "site",
        # Historically flaky in some packaging environments.
        "regex",
    ]
    if heavy:
        modules.extend(["spacy", "thinc", "torch", "transformers", "kokoro"])

    failures: list[str] = []
    for name in modules:
        try:
            import_module(name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"IMPORT {name}: {exc!r}")
            # Optional extra context: dist metadata version lookup.
            try:
                ver = dist_version(name)
                failures.append(f"DIST {name}: {ver}")
            except Exception as exc2:  # noqa: BLE001
                failures.append(f"DIST {name}: {exc2!r}")

    if failures:
        return 2, "\n".join(failures)

    return 0, "OK"


def program_base_dir(*, argv0: object, cwd: Callable[[], Path]) -> Path:
    """Derive a directory to write logs beside the executable (best-effort)."""

    try:
        # Preserve the old behaviour: invalid argv0 types should fall back to cwd.
        if argv0 is None:
            raise TypeError("argv0 is None")
        if not isinstance(argv0, (str, Path)):
            raise TypeError(f"argv0 has invalid type: {type(argv0)!r}")
        return Path(argv0).resolve().parent
    except Exception:
        return cwd()


def append_startup_log(
    *,
    base_dir: Path,
    filename: str,
    text: str,
    open_fn: Callable[..., ContextManager[IO[str]]],
) -> None:
    try:
        path = base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open_fn(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(text.rstrip("\n") + "\n")
    except Exception:
        return


def ensure_stdio(
    *,
    base_dir: Path,
    stdout: object,
    stderr: object,
    open_fn: Callable[..., Any],
) -> tuple[object, object]:
    """Ensure stdout/stderr exist for GUI builds.

    Returns updated (stdout, stderr).
    """

    if stdout is None:
        try:
            stdout = open_fn(
                base_dir / "NarrateX.runtime.out.txt",
                "a",
                buffering=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass

    if stderr is None:
        try:
            stderr = open_fn(
                base_dir / "NarrateX.runtime.err.txt",
                "a",
                buffering=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass

    return stdout, stderr
