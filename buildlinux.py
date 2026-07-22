"""Linux PyInstaller builder for the NarrateX application.

Produces a self-contained onedir bundle in dist-pyinstaller/NarrateX/.
The bundle includes Python, Qt, and all dependencies - no system Python needed.

Usage:
    source venv/bin/activate
    python buildlinux.py
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
ICON_PNG = PROJECT_ROOT / "narratex.png"


def _run(cmd: list[str]) -> None:
    print("\n> " + " ".join(cmd))

    phases = [
        ("analysis", ("checking Analysis", "Running Analysis", "Building Analysis")),
        ("pyz", ("checking PYZ", "Building PYZ")),
        ("pkg", ("checking PKG", "Building PKG")),
        ("exe", ("checking EXE", "Building EXE")),
        ("collect", ("checking COLLECT", "Building COLLECT")),
    ]
    phase_index = 0
    phase_name = phases[0][0]
    heartbeat_s = float(os.getenv("NARRATEX_BUILD_HEARTBEAT_S", "5") or "5")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None

    start = last_output_at = time.monotonic()
    last_line = ""

    try:
        while True:
            line = proc.stdout.readline()
            if line:
                last_output_at = time.monotonic()
                last_line = line.strip()
                for i, (name, markers) in enumerate(phases):
                    if any(m in line for m in markers):
                        phase_index = max(phase_index, i)
                        phase_name = phases[phase_index][0]
                        break
                print(line, end="")
            else:
                if proc.poll() is not None:
                    break
                now = time.monotonic()
                if now - last_output_at >= heartbeat_s:
                    elapsed = int(now - start)
                    pct = int(((phase_index + 1) / len(phases)) * 100)
                    tail = (
                        (last_line[:140] + "…") if len(last_line) > 140 else last_line
                    )
                    info = (
                        f"[build] {phase_name} "
                        f"({phase_index + 1}/{len(phases)} ~{pct}%) "
                        f"elapsed={elapsed}s"
                    )
                    if tail:
                        print(f"{info} | {tail}")
                    else:
                        print(info)
                    last_output_at = now
                time.sleep(0.1)
    except KeyboardInterrupt:
        proc.terminate()
        raise

    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


def _ensure_spacy_model() -> None:
    """Download en_core_web_sm if not already installed."""
    try:
        import en_core_web_sm  # noqa: F401
    except ImportError:
        print("Downloading spacy model en_core_web_sm...")
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
            check=True,
        )


def main() -> int:
    if os.name == "nt":
        raise SystemExit(
            "buildlinux.py is Linux/macOS only - use buildexe.py on Windows"
        )

    if not ENTRYPOINT.exists():
        raise SystemExit(f"Entrypoint not found: {ENTRYPOINT}")
    if not ICON_PNG.exists():
        raise SystemExit(f"Icon not found: {ICON_PNG}")

    _ensure_spacy_model()

    dist_root = PROJECT_ROOT / "dist-pyinstaller"
    work_root = PROJECT_ROOT / "build" / "pyinstaller"

    for p in [work_root, dist_root]:
        if p.exists():
            shutil.rmtree(p)

    log_level = os.getenv("NARRATEX_PYINSTALLER_LOG_LEVEL", "INFO").strip().upper()

    # Linux uses ':' as the path separator in --add-data (Windows uses ';')
    add_data = [
        f"{PROJECT_ROOT / 'LICENSE'}:.",
        f"{PROJECT_ROOT / 'LGPL3-LICENSE'}:.",
        f"{PROJECT_ROOT / 'narratex.png'}:.",
        f"{PROJECT_ROOT / 'narratex_16.png'}:.",
        f"{PROJECT_ROOT / 'narratex_32.png'}:.",
        f"{PROJECT_ROOT / 'narratex_48.png'}:.",
        f"{PROJECT_ROOT / 'narratex_64.png'}:.",
        f"{PROJECT_ROOT / 'narratex_128.png'}:.",
        f"{PROJECT_ROOT / 'narratex_256.png'}:.",
        f"{PROJECT_ROOT / 'narratex_512.png'}:.",
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
        str(ICON_PNG),
        "--collect-all=kokoro",
        "--hidden-import=misaki",
        "--collect-data=misaki",
        "--collect-all=phonemizer",
        "--collect-all=espeakng_loader",
        "--collect-all=spacy",
        "--collect-all=en_core_web_sm",
        "--collect-data=language_tags",
        "--collect-binaries=torch",
        "--collect-data=torch",
        "--hidden-import=torch",
        "--collect-all=transformers",
        "--collect-all=numpy",
        "--collect-all=soundfile",
        "--hidden-import=soundfile",
        "--collect-binaries=soundfile",
        "--exclude-module=tensorboard",
        "--exclude-module=torch.utils.tensorboard",
        "--exclude-module=torch.distributed._sharding_spec",
        "--exclude-module=torch.distributed._sharded_tensor",
        "--exclude-module=torch.distributed._shard.checkpoint",
        "--hidden-import=torch.distributed.rpc",
        "--exclude-module=scipy",
        # Exclude CUDA/GPU packages - NarrateX runs on CPU only.
        # Without these exclusions PyInstaller bundles ~4 GB of nvidia libraries.
        "--exclude-module=nvidia",
        "--exclude-module=triton",
        "--exclude-module=cuda_bindings",
        "--exclude-module=cuda_pathfinder",
    ]

    wiring_hidden_imports = [
        "voice_reader.application.services.narration_service",
        "voice_reader.application.services.bookmark_service",
        "voice_reader.application.services.idea_map_service",
        "voice_reader.application.services.idea_indexing_manager",
        "voice_reader.application.services.structural_bookmark_service",
        "voice_reader.application.services.voice_profile_service",
        "voice_reader.domain.services.chunking_service",
        "voice_reader.infrastructure.tts.tts_engine_factory",
        "voice_reader.infrastructure.books.cover_extractor",
        "voice_reader.infrastructure.audio.audio_streamer",
        "voice_reader.infrastructure.books.converter",
        "voice_reader.infrastructure.books.parser",
        "voice_reader.infrastructure.books.repository",
        "voice_reader.infrastructure.cache.filesystem_cache",
        "voice_reader.infrastructure.bookmarks.json_bookmark_repository",
        "voice_reader.infrastructure.ideas.json_idea_index_repository",
        "voice_reader.infrastructure.preferences.json_preferences_repository",
        "voice_reader.infrastructure.tts.voice_profile_repository",
        "voice_reader.ui.main_window",
        "voice_reader.ui.ui_controller",
    ]
    for mod in wiring_hidden_imports:
        cmd.append(f"--hidden-import={mod}")

    for spec in add_data:
        cmd.extend(["--add-data", spec])

    cmd.append(str(ENTRYPOINT))

    _run(cmd)

    exe = dist_root / "NarrateX" / "NarrateX"
    if not exe.exists():
        print(
            "\nBuild finished but expected binary not found. Inspect dist-pyinstaller/."
        )
        return 1

    internal = dist_root / "NarrateX" / "_internal"

    # Strip CUDA/GPU libraries - the app runs CPU-only (device="cpu") and torch
    # falls back gracefully when CUDA libs are absent.  Removing these cuts the
    # bundle from ~7 GB to ~1 GB with no runtime impact.
    for cuda_dir in ["nvidia", "triton", "cuda_bindings", "cuda_pathfinder"]:
        target = internal / cuda_dir
        if target.exists():
            shutil.rmtree(target)
            print(f"  Stripped {cuda_dir}/ (CUDA - not needed on CPU)")

    # Strip host-collected glib system libraries.  PyInstaller picks these up
    # from the host (glibc 2.43) which is newer than the flatpak runtime's
    # glibc.  Removing them lets the flatpak runtime provide its own compatible
    # versions.  PySide6 manylinux wheels are compiled against glibc 2.17+ so
    # they work with whatever the runtime supplies.
    import glob as _glob

    glib_patterns = [
        "libglib-2.0.so*",
        "libgthread-2.0.so*",
        "libgmodule-2.0.so*",
        "libgobject-2.0.so*",
        "libgio-2.0.so*",
    ]
    for pattern in glib_patterns:
        for match in _glob.glob(str(internal / pattern)):
            Path(match).unlink()
            print(
                f"  Stripped {Path(match).name} "
                "(host glib - runtime provides compatible version)"
            )

    print(f"\nBuilt: {exe}  ({_dir_size(dist_root / 'NarrateX')})")
    return 0


def _dir_size(path: Path) -> str:
    import subprocess as _sp

    result = _sp.run(["du", "-sh", str(path)], capture_output=True, text=True)
    return result.stdout.split()[0] if result.returncode == 0 else "?"


if __name__ == "__main__":
    raise SystemExit(main())
