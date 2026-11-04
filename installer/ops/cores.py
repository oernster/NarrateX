"""How many threads the payload work may use on this machine.

Compressing and unpacking LZMA, hashing and CRC all release the GIL on large
buffers, so plain threads use every core. A machine with one core gets one
thread: the serial path, with no pool. So does one that cannot say how many.
"""

from __future__ import annotations

import os


def usable_cores() -> int:
    """The cores this process may run on; never fewer than one."""

    # process_cpu_count (3.13) honours an affinity mask; cpu_count does not.
    counter = getattr(os, "process_cpu_count", None) or os.cpu_count
    return max(1, counter() or 1)
