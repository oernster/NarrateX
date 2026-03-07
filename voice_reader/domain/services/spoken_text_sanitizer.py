"""Domain service to sanitize text before sending to TTS.

Purpose: remove structural numbering ("1", "1.1.2") and numbering prefixes so the
listener doesn't hear outline junk while keeping UI highlighting based on the
original text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_ONLY = re.compile(r"^\s*\d+(?:\.\d+)*\s*$")
_NUMBER_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\s+")


@dataclass(frozen=True, slots=True)
class SpokenTextSanitizer:
    def sanitize(self, text: str) -> str:
        # Operate line-by-line to preserve some structure while dropping
        # outline numbering.
        lines: list[str] = []
        for raw in text.splitlines():
            if _NUMBER_ONLY.match(raw):
                continue
            cleaned = _NUMBER_PREFIX.sub("", raw)
            cleaned = cleaned.strip()
            if cleaned:
                lines.append(cleaned)
        return "\n".join(lines).strip()
