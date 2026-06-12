"""Ensure phonemizer can locate an espeak-ng library and its data directory.

misaki 0.7.4 only auto-configures espeak on macOS and Windows; on Linux it
relies on a system-wide ``libespeak-ng``. In sandboxed or packaged
environments (for example Flatpak) no system library is present, so
out-of-dictionary words make the English G2P fallback emit ``None`` phonemes
and synthesis fails with::

    unsupported operand type(s) for +: 'NoneType' and 'str'

When no espeak library is discoverable we point phonemizer at the bundled
``espeakng_loader`` library and its data directory via environment variables.
A working system installation is never overridden.
"""

from __future__ import annotations

import os

# phonemizer reads the library path from this variable; the espeak-ng C library
# reads its data directory (voices, phoneme tables) from ESPEAK_DATA_PATH.
_LIBRARY_ENV = "PHONEMIZER_ESPEAK_LIBRARY"
_DATA_ENV = "ESPEAK_DATA_PATH"


def _load_espeak_wrapper():
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    return EspeakWrapper


def _load_espeakng_loader():
    import espeakng_loader

    return espeakng_loader


def configure_espeak() -> None:
    """Point phonemizer at a usable espeak-ng library when none is found.

    Idempotent and safe to call repeatedly. No-op when phonemizer already has a
    discoverable library (e.g. a system install) or when the override is already
    configured via the environment.
    """

    if os.environ.get(_LIBRARY_ENV):
        return

    try:
        wrapper = _load_espeak_wrapper()
    except Exception:
        return

    try:
        wrapper.library()
        return
    except Exception:
        pass

    try:
        loader = _load_espeakng_loader()
    except Exception:
        return

    os.environ[_LIBRARY_ENV] = str(loader.get_library_path())
    os.environ.setdefault(_DATA_ENV, str(loader.get_data_path()))
