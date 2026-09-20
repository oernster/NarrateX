"""The shelf's infrastructure: the disk, read through the ports.

One implementation per port: the walker that finds book files, the metadata
reader that says what one states, the SQLite index that remembers it, the
thumbnail cache the grid draws from, the cover reader that fills that cache and
the reducer that makes each small copy. Nothing above this package imports any of
them; the composition root wires them in.
"""

from voice_reader.infrastructure.shelf.cover_reader import ShelfCoverReader
from voice_reader.infrastructure.shelf.index_store import SqliteShelfIndex
from voice_reader.infrastructure.shelf.metadata_reader import ShelfMetadataReader
from voice_reader.infrastructure.shelf.thumbnailer import QtThumbnailMaker
from voice_reader.infrastructure.shelf.thumbnails import FileThumbnailStore
from voice_reader.infrastructure.shelf.walker import FileSystemWalker

__all__ = [
    "FileSystemWalker",
    "FileThumbnailStore",
    "QtThumbnailMaker",
    "ShelfCoverReader",
    "ShelfMetadataReader",
    "SqliteShelfIndex",
]
