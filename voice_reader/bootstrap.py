"""Composition root helper.

This module exists to keep entrypoints small while still making wiring explicit.

Hard rule enforced by structural tests:
- Only entrypoints (e.g. [`main()`](app.py:176) and installer entrypoints) may
  import [`voice_reader.bootstrap`](voice_reader/bootstrap.py:1).
- Other modules must not depend on this module.
"""

from __future__ import annotations


def _touch() -> None:
    """Coverage helper.

    This module will be fleshed out as wiring moves from UI into the composition root.
    Keeping a tiny function makes it trivial to cover under the existing 100% gate.
    """

    return
