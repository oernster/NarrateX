"""The bookshelf's domain: what a work is, how it is identified, how it is filed.

Pure rules over strings and small value objects. Nothing here reads a file,
reads a clock or knows a framework exists. The specification these serve is
BOOKSHELF.md at the repository root; each module names the requirements it
carries.
"""

from voice_reader.domain.shelf.corpus import resolve_author_first
from voice_reader.domain.shelf.genres import GenreReading
from voice_reader.domain.shelf.identity import ShelfEntry, ShelfKey
from voice_reader.domain.shelf.progress import Progress, ReadingState
from voice_reader.domain.shelf.works import Work

__all__ = [
    "GenreReading",
    "Progress",
    "ReadingState",
    "ShelfEntry",
    "ShelfKey",
    "Work",
    "resolve_author_first",
]
