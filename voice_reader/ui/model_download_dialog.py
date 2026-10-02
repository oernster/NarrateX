"""First-run Kokoro model + voice download with a determinate Qt progress bar.

Called once at startup when any model weight or voice file is not yet cached.
Progress is captured by temporarily replacing the tqdm class used inside
huggingface_hub.file_download with a Qt-signal-emitting subclass.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from tqdm import tqdm as _BaseTqdm
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog

_REPO_ID = "hexgrad/Kokoro-82M"

# Where each stage of the download ends on the progress bar, in percent. The
# voices share whatever is left after the weights, up to the full bar.
_CONFIG_END_PCT = 2
_WEIGHTS_END_PCT = 62
_FULL_PCT = 100


def download_steps(voice_ids: Sequence[str]) -> tuple[tuple[str, int], ...]:
    """Every file the first run fetches, each with its progress end percent.

    The voice IDs arrive from the composition root, which reads them from the
    same repository the voice picker lists, so every voice a reader can choose
    is fetched here and none is left for Kokoro to download mid-read.
    """

    n = len(voice_ids)
    span = _FULL_PCT - _WEIGHTS_END_PCT
    return (
        ("config.json", _CONFIG_END_PCT),
        ("kokoro-v1_0.pth", _WEIGHTS_END_PCT),
        *(
            (f"voices/{v}.pt", _WEIGHTS_END_PCT + int((i + 1) * span / n))
            for i, v in enumerate(voice_ids)
        ),
    )


def _hf_cache_root() -> Path:
    """Return the HuggingFace cache root without importing huggingface_hub."""
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".cache"
    # Respect HF_HOME / HUGGINGFACE_HUB_CACHE if set
    hf_home = os.environ.get("HF_HOME", "")
    if hf_home:
        return Path(hf_home) / "hub"
    hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE", "")
    if hub_cache:
        return Path(hub_cache)
    return base / "huggingface" / "hub"


def _is_cached(filename: str) -> bool:
    """Check whether a file exists in the HF cache without importing huggingface_hub."""
    repo_dir = _hf_cache_root() / "models--hexgrad--Kokoro-82M"
    snapshots = repo_dir / "snapshots"
    if not snapshots.exists():
        return False
    return any(
        (snap / filename).exists() for snap in snapshots.iterdir() if snap.is_dir()
    )


def model_is_ready(voice_ids: Sequence[str]) -> bool:
    """True only when every model weight and voice file is already cached."""
    return all(_is_cached(fname) for fname, _ in download_steps(voice_ids))


# ---------------------------------------------------------------------------
# tqdm shim - routes per-chunk progress to a Qt signal
# ---------------------------------------------------------------------------


class _QtTqdm(_BaseTqdm):
    _progress_signal: "Signal | None" = None
    _range_start: int = 0
    _range_end: int = 100

    def __init__(self, *args, **kwargs):
        kwargs["disable"] = True
        super().__init__(*args, **kwargs)

    def update(self, n: int = 1) -> None:
        super().update(n)
        sig = _QtTqdm._progress_signal
        if sig is not None and self.total and self.total > 0:
            frac = min(1.0, self.n / self.total)
            span = _QtTqdm._range_end - _QtTqdm._range_start
            pct = int(_QtTqdm._range_start + frac * span)
            sig.emit(pct, "")

    def close(self) -> None:
        sig = _QtTqdm._progress_signal
        if sig is not None:
            sig.emit(_QtTqdm._range_end, "")
        super().close()


# ---------------------------------------------------------------------------
# Pre-warm thread - imports huggingface_hub in background so the main thread
# stays free to process Wayland/X11 compositor pings (prevents GNOME "not
# responding").  Uses a processEvents busy-loop rather than QEventLoop.exec()
# because the latter can silently swallow compositor events on some compositors.
# ---------------------------------------------------------------------------


class _PrewarmThread(QThread):
    ready: Signal = Signal()

    def run(self) -> None:
        import importlib

        for _m in (
            "requests",
            "urllib3",
            "certifi",
            "huggingface_hub",
            "huggingface_hub.file_download",
        ):
            try:
                importlib.import_module(_m)
            except Exception:
                pass
        self.ready.emit()


# ---------------------------------------------------------------------------
# Download thread
# ---------------------------------------------------------------------------


class _DownloadThread(QThread):
    progress: Signal = Signal(int, str)
    all_done: Signal = Signal()
    failed: Signal = Signal(str)

    def __init__(self, steps: tuple[tuple[str, int], ...]) -> None:
        super().__init__()
        self._steps = steps

    def run(self) -> None:
        try:
            from huggingface_hub import hf_hub_download
            import huggingface_hub.file_download as _hfd

            _orig_tqdm = getattr(_hfd, "tqdm", None)
            _hfd.tqdm = _QtTqdm  # type: ignore[attr-defined]
            _QtTqdm._progress_signal = self.progress

            try:
                prev_end = 0
                for fname, end_pct in self._steps:
                    if _is_cached(fname):
                        self.progress.emit(end_pct, "")
                        prev_end = end_pct
                        continue

                    _QtTqdm._range_start = prev_end
                    _QtTqdm._range_end = end_pct
                    short = fname.split("/")[-1]
                    self.progress.emit(prev_end, f"Downloading {short}…")
                    hf_hub_download(repo_id=_REPO_ID, filename=fname)
                    prev_end = end_pct
            finally:
                _QtTqdm._progress_signal = None
                if _orig_tqdm is not None:
                    _hfd.tqdm = _orig_tqdm  # type: ignore[attr-defined]

            self.all_done.emit()

        except Exception as exc:
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def maybe_download_model(app, voice_ids: Sequence[str]) -> bool:  # noqa: ANN001
    """Show a determinate progress dialog to download the Kokoro model and voices.

    `voice_ids` is every voice the picker offers; each is fetched here so that
    narration never reaches the network after the first run.

    Uses a direct filesystem check (no huggingface_hub import) for model_is_ready()
    so the fast-path (model already cached) returns in microseconds.

    If a download is needed, pre-warms huggingface_hub imports in a background
    thread while keeping the main thread in a processEvents() busy-loop so the
    splash window continues to respond to GNOME/Wayland compositor pings.
    """
    if model_is_ready(voice_ids):
        return True

    # Pre-warm huggingface_hub imports in a background thread.
    # Keep the main thread busy with processEvents() rather than blocking -
    # this answers compositor pings and prevents the GNOME "not responding" dialog.
    _prewarm_done: list[bool] = []

    def _mark_done() -> None:
        _prewarm_done.append(True)

    _pw = _PrewarmThread()
    _pw.ready.connect(_mark_done)
    _pw.start()

    while not _prewarm_done:
        app.processEvents()  # drains ALL pending events, including Wayland pings

    _pw.wait()

    # ----- Download dialog -----

    dlg = QProgressDialog(
        "NarrateX: Downloading voice model\n\nPreparing…", None, 0, 100
    )
    dlg.setWindowTitle("NarrateX")
    # FramelessWindowHint is the only flag Wayland/GNOME honours for removing
    # the title-bar decoration.  CustomizeWindowHint is ignored under GNOME
    # server-side decorations - the compositor draws its own buttons including
    # the minimize button (rendered as an em dash in the Ubuntu Yaru theme).
    # Going frameless removes all of that; the label carries the context instead.
    dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    dlg.setMinimumWidth(480)
    dlg.setMinimumDuration(0)
    dlg.setCancelButton(None)
    dlg.setValue(0)

    _error: list[str] = []

    def _on_progress(pct: int, label: str) -> None:
        dlg.setValue(pct)
        if label:
            dlg.setLabelText(
                "NarrateX: Downloading voice model\n\n"
                f"{label}\n\n"
                "This only happens once. Everything is cached afterwards."
            )

    def _on_failed(msg: str) -> None:
        _error.append(msg)
        dlg.reject()

    thread = _DownloadThread(download_steps(voice_ids))
    thread.progress.connect(_on_progress)
    thread.all_done.connect(dlg.accept)
    thread.failed.connect(_on_failed)

    thread.start()
    dlg.exec()
    thread.wait()

    if _error:
        box = QMessageBox(None)
        box.setWindowTitle("Download failed")
        box.setIcon(QMessageBox.Critical)
        box.setText(
            f"Could not download the Kokoro voice model:\n\n{_error[0]}"
            "\n\nCheck your internet connection and try again."
        )
        box.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        box.exec()
        return False

    return model_is_ready(voice_ids)
