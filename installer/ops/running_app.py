"""Detect whether NarrateX is currently running."""

from __future__ import annotations

from pathlib import Path

import psutil


def is_app_running(exe_path: Path) -> bool:
    exe_path = exe_path.resolve()
    for proc in psutil.process_iter(attrs=["exe"]):
        try:
            pexe = proc.info.get("exe")
            if not pexe:
                continue
            if Path(pexe).resolve() == exe_path:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:  # noqa: BLE001
            # Degrades to this one process being treated as not ours. Process
            # inspection fails in many shapes on Windows (a process exiting
            # mid-scan, a path that will not resolve); none of them is a
            # reason to abandon the scan of every other process.
            continue
    return False
