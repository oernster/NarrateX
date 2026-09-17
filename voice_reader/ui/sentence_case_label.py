"""A label whose text always opens with a capital letter.

The status line is written from many places: narration states (whose bare
status names are lower case), controllers and error paths. Capitalising here,
once, constrains every writer rather than relying on each one remembering.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel


def sentence_case(text: str) -> str:
    """`text` with its first character upper-cased and the rest untouched."""

    return text[:1].upper() + text[1:]


class SentenceCaseLabel(QLabel):
    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        super().setText(sentence_case(str(text)))
