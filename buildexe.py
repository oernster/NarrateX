"""Windows-only PyInstaller builder for the NarrateX application EXE.

Goal: produce a runnable Windows GUI executable as fast as possible.

Usage (PowerShell):

    venv/Scripts/Activate.ps1
    python buildexe.py

Output:

    dist-pyinstaller/NarrateX/NarrateX.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENTRYPOINT = PROJECT_ROOT / "app.py"
ICON_ICO = PROJECT_ROOT / "narratex.ico"


def _require_windows() -> None:
    if os.name != "nt":
        raise SystemExit("buildexe.py is Windows-only")


def _run(cmd: list[str]) -> None:
    print("\n> " + " ".join(cmd))

    # PyInstaller can run for a long time with little/no console output,
    # especially when log-level is WARN. Stream output when available and emit a
    # periodic heartbeat so builds don't look "stuck".
    start = time.monotonic()
    last_output_at = start
    last_line: str = ""

    phases = [
        ("analysis", ("checking Analysis", "Running Analysis", "Building Analysis")),
        ("pyz", ("checking PYZ", "Building PYZ")),
        ("pkg", ("checking PKG", "Building PKG")),
        ("exe", ("checking EXE", "Building EXE")),
        ("collect", ("checking COLLECT", "Building COLLECT")),
    ]
    phase_index = 0
    phase_name = phases[phase_index][0]

    heartbeat_s = float(os.getenv("NARRATEX_BUILD_HEARTBEAT_S", "5").strip() or "5")

    proc = subprocess.Popen(  # noqa: S603 - intended subprocess execution
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None  # for type-checkers

    try:
        while True:
            line = proc.stdout.readline()
            if line:
                last_output_at = time.monotonic()
                last_line = line.strip()

                # Best-effort phase tracking for a simple progress indicator.
                for i, (name, markers) in enumerate(phases):
                    if any(m in line for m in markers):
                        phase_index = max(phase_index, i)
                        phase_name = phases[phase_index][0]
                        break

                # Avoid double newlines (line already includes one)
                print(line, end="")
            else:
                if proc.poll() is not None:
                    break

                now = time.monotonic()
                if now - last_output_at >= heartbeat_s:
                    elapsed_s = int(now - start)
                    tail = (last_line[:140] + "…") if len(last_line) > 140 else last_line
                    pct = int(((phase_index + 1) / len(phases)) * 100)
                    if tail:
                        print(
                            f"[build] {phase_name} ({phase_index + 1}/{len(phases)} ~{pct}%) "
                            f"elapsed={elapsed_s}s | last: {tail}"
                        )
                    else:
                        print(
                            f"[build] {phase_name} ({phase_index + 1}/{len(phases)} ~{pct}%) "
                            f"elapsed={elapsed_s}s"
                        )
                    last_output_at = now

                time.sleep(0.1)
    except KeyboardInterrupt:
        # Propagate Ctrl+C but attempt a clean stop first.
        proc.terminate()
        raise

    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


def main() -> int:
    _require_windows()

    if not ENTRYPOINT.exists():
        raise SystemExit(f"Entrypoint not found: {ENTRYPOINT}")
    if not ICON_ICO.exists():
        raise SystemExit(f"Icon not found: {ICON_ICO}")

    dist_root = PROJECT_ROOT / "dist-pyinstaller"
    work_root = PROJECT_ROOT / "build" / "pyinstaller"

    # Clean prior PyInstaller outputs.
    for p in [work_root, dist_root, PROJECT_ROOT / "NarrateX.spec"]:
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    p.unlink()
                except Exception:
                    pass

    # Fast, reliable baseline: onedir build.
    log_level = os.getenv("NARRATEX_PYINSTALLER_LOG_LEVEL", "INFO").strip().upper()

    # Ship runtime icon assets into the onedir bundle so Qt can load them at
    # runtime for the taskbar/titlebar icon.
    #
    # Note: `--icon` only affects the *embedded* exe icon (Explorer/Start Menu).
    # The running taskbar button typically uses the Qt window icon.
    add_data = [
        # Licences (shown in-app via top-right licence buttons).
        f"{PROJECT_ROOT / 'LICENSE'};.",
        f"{PROJECT_ROOT / 'LGPL3-LICENSE'};.",
        f"{PROJECT_ROOT / 'narratex.ico'};.",
        f"{PROJECT_ROOT / 'narratex_16.png'};.",
        f"{PROJECT_ROOT / 'narratex_32.png'};.",
        f"{PROJECT_ROOT / 'narratex_48.png'};.",
        f"{PROJECT_ROOT / 'narratex_64.png'};.",
        f"{PROJECT_ROOT / 'narratex_128.png'};.",
        f"{PROJECT_ROOT / 'narratex_256.png'};.",
        f"{PROJECT_ROOT / 'narratex_512.png'};.",
    ]
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--log-level={log_level}",
        "--name",
        "NarrateX",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(work_root),
        "--specpath",
        str(PROJECT_ROOT),
        "--windowed",
        "--icon",
        str(ICON_ICO),

        # Collect package data for components that rely on data files.
        "--collect-all=kokoro",
        # NOTE: Do *not* use --collect-all=misaki.
        # PyInstaller's collection step tries importing optional language cleaners
        # (e.g. misaki.vi_cleaner) which may depend on extra packages not shipped
        # with NarrateX (e.g. 'vietnam_number'), resulting in noisy warnings.
        # Kokoro imports misaki as a normal dependency, so standard analysis is
        # sufficient; keep a hidden-import as an extra safety net.
        "--hidden-import=misaki",
        # misaki loads accent dictionaries from package data files like
        # `misaki/data/gb_gold.json`. Without explicitly collecting data, the
        # frozen app fails at runtime with:
        #   FileNotFoundError: .../_internal/misaki/data/gb_gold.json
        "--collect-data=misaki",
        "--collect-all=phonemizer",
        "--collect-all=espeakng_loader",
        "--collect-all=spacy",
        "--collect-all=en_core_web_sm",

        # Required at runtime by `segments` -> `csvw` -> `language_tags`.
        # If omitted, the frozen app fails with:
        #   FileNotFoundError: .../_internal/language_tags/data/json/index.json
        "--collect-data=language_tags",

        # PyInstaller already has a robust built-in hook for torch.
        # Avoid --collect-all=torch: it forces PyInstaller to import/scan a huge
        # submodule surface (including deprecated compat modules) during
        # analysis, producing warnings like:
        #   DeprecationWarning: `torch.distributed._sharding_spec` will be deprecated
        # Instead, collect just torch's data + binaries and rely on the hook.
        "--collect-binaries=torch",
        "--collect-data=torch",
        "--hidden-import=torch",
        "--collect-all=transformers",

        # Optional extras referenced by torch hooks; exclude to avoid warnings
        # and reduce output size.
        "--exclude-module=tensorboard",
        "--exclude-module=torch.utils.tensorboard",

        # Avoid importing/packaging torch distributed compatibility shims that
        # emit deprecation warnings during PyInstaller analysis.
        # NOTE:
        # Do NOT exclude `torch.distributed` entirely.
        # Even for inference-only apps, torch imports `torch.distributed.rpc`
        # indirectly via `torch._jit_internal`.
        # If we exclude the whole package, the frozen app fails at runtime with:
        #   ModuleNotFoundError: No module named 'torch.distributed.rpc'
        "--exclude-module=torch.distributed._sharding_spec",
        "--exclude-module=torch.distributed._sharded_tensor",
        "--exclude-module=torch.distributed._shard.checkpoint",
        # Keep RPC available; include explicitly to make packaging intent clear.
        "--hidden-import=torch.distributed.rpc",

        # scipy is not a dependency of NarrateX, but some packages include
        # optional scipy integrations. Exclude it explicitly to avoid PyInstaller
        # attempting to run hook-scipy.py in environments without scipy.
        "--exclude-module=scipy",
    ]

    for spec in add_data:
        cmd.extend(["--add-data", spec])

    # Important: the script/entrypoint must come last. Any options appended
    # after it will be treated as script arguments and ignored by PyInstaller.
    cmd.append(str(ENTRYPOINT))

    _run(cmd)

    exe = dist_root / "NarrateX" / "NarrateX.exe"
    if exe.exists():
        print(f"\nBuilt: {exe}")
        return 0

    print("\nBuild finished; expected EXE not found. Inspect dist-pyinstaller/.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

