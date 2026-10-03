"""Decoding a plain-text or Markdown book's bytes or refusing with a reason.

The order: a byte order mark names its encoding outright; otherwise strict
UTF-8; otherwise Windows-1252, the legacy Windows code page for Western
text. Each decode is strict, so a letter is never dropped in silence: bytes
no candidate reads cleanly refuse the book and say why.

UTF-32 marks are checked before UTF-16 ones because the UTF-32 little-endian
mark begins with the UTF-16 little-endian mark.
"""

from __future__ import annotations

import codecs

from voice_reader.shared.errors import BookParseError

_MARKED: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

_UNMARKED: tuple[str, ...] = ("utf-8", "cp1252")

_REFUSAL = (
    "This text file is in an encoding NarrateX cannot read. "
    "Save it as UTF-8 and open it again."
)


def decode_book_text(data: bytes) -> str:
    """The text these bytes hold; raises BookParseError when none reads cleanly."""

    for mark, codec in _MARKED:
        if data.startswith(mark):
            return _strict(data[len(mark) :], (codec,))
    return _strict(data, _UNMARKED)


def _strict(data: bytes, codecs_to_try: tuple[str, ...]) -> str:
    for codec in codecs_to_try:
        try:
            return data.decode(codec)
        except UnicodeDecodeError:
            continue
    raise BookParseError(_REFUSAL)
