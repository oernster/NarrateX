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

# Supported interpreter window.
#
# The upper bound is not caution, it is a hard constraint: `kokoro` pins
# >=3.10,<3.13, so a virtual environment built on a newer interpreter cannot
# resolve `requirements.txt` at all. When that happens pip fails deep into a
# resolve with no mention of the interpreter, which is why this check exists
# rather than relying on `requires-python` (which pip never reads for a
# `-r requirements.txt` install).
MIN_SUPPORTED_PYTHON = (3, 10)
FIRST_UNSUPPORTED_PYTHON = (3, 13)


def unsupported_python_message(version: tuple[int, ...]) -> str | None:
    """Return an actionable message when the interpreter is out of range.

    Returns None when `version` is supported, so the caller reads as a guard.
    """

    current = tuple(version[:2])
    if MIN_SUPPORTED_PYTHON <= current < FIRST_UNSUPPORTED_PYTHON:
        return None

    def _render(parts: tuple[int, ...]) -> str:
        return ".".join(str(part) for part in parts)

    supported = (
        f"{_render(MIN_SUPPORTED_PYTHON)} to {_render(FIRST_UNSUPPORTED_PYTHON)}"
    )
    return (
        f"NarrateX needs Python {supported} (exclusive), "
        f"but this interpreter is {_render(current)}.\n"
        "The kokoro speech engine does not publish wheels outside that range, "
        "so the dependencies cannot install here.\n"
        "Rebuild the virtual environment against a supported interpreter, "
        "for example:\n"
        "    py -3.11 -m venv venv"
    )


def enforce_supported_python(
    version: tuple[int, ...],
    *,
    write: Callable[[str], None],
) -> None:
    """Stop the program when the interpreter is outside the supported window.

    Kept here rather than inline at the entrypoint so the behaviour is tested
    and the entrypoint stays a single call before its heavy imports.
    """

    message = unsupported_python_message(version)
    if message is None:
        return
    write(message)
    raise SystemExit(1)


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
