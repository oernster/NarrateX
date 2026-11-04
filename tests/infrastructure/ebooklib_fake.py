"""A stand-in for `ebooklib.epub`, for tests that inject EbookLib as a module.

The parser reads through `epub_reader`, which builds its reader on
`ebooklib.epub.EpubReader`; the fake reader answers whatever `read` answers
for the path and options it was given.
"""

from __future__ import annotations

import types
from collections.abc import Callable


def fake_epub(read: Callable[..., object]) -> types.SimpleNamespace:
    """An `ebooklib.epub` whose reader loads the book `read(path, options)`."""

    class EpubReader:
        def __init__(self, path: str, options: dict | None = None) -> None:
            self._path = path
            self._options = options

        def load(self) -> object:
            return read(self._path, options=self._options)

        def process(self) -> None:
            return None

    return types.SimpleNamespace(EpubReader=EpubReader)
