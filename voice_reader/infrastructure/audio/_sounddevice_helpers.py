"""SoundDevice helper functions.

Separated to keep `SoundDeviceAudioStreamer` compact.
"""

from __future__ import annotations


def safe_output_device(sd) -> int | None:
    """Return a safe PortAudio output device index or None.

    On some Windows machines `sd.default.device` resolves to -1 (or a scalar
    wrapping -1). Passing `device=-1` causes PortAudioError.
    """

    out_dev = None
    try:
        default_dev = getattr(sd.default, "device", None)
        if isinstance(default_dev, (list, tuple)) and len(default_dev) >= 2:
            out_dev = default_dev[1]
        else:
            out_dev = default_dev
    except Exception:
        out_dev = None

    try:
        if out_dev is None:
            return None
        out_dev_int = int(out_dev)
    except Exception:
        return None

    if out_dev_int < 0:
        return None

    # Validate when possible.
    try:
        if hasattr(sd, "query_devices"):
            sd.query_devices(out_dev_int)
    except Exception:
        return None

    return out_dev_int


def sd_play(sd, *, data, sr: int, blocking: bool, device: int | None) -> None:
    """Play audio with sounddevice, retrying without device on device errors."""

    if device is None:
        sd.play(data, sr, blocking=blocking)
        return

    try:
        sd.play(data, sr, blocking=blocking, device=device)
    except TypeError:
        # Older sounddevice versions may not accept device=.
        sd.play(data, sr, blocking=blocking)
    except Exception as exc:
        msg = str(exc).lower()
        # Fallback: if explicit device selection is broken, retry without it.
        if "querying device" in msg or "device" in msg:
            sd.play(data, sr, blocking=blocking)
        else:
            raise
