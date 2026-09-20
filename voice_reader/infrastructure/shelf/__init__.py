"""The shelf's infrastructure: the disk, read through the ports.

Four implementations, one per port: the walker that finds book files, the
metadata reader that says what one states, the SQLite index that remembers it
and the thumbnail cache the grid draws from. Nothing above this package imports
any of them; the composition root wires them in.
"""

from voice_reader.infrastructure.shelf.index_store import SqliteShelfIndex
from voice_reader.infrastructure.shelf.metadata_reader import ShelfMetadataReader
from voice_reader.infrastructure.shelf.thumbnails import FileThumbnailStore
from voice_reader.infrastructure.shelf.walker import FileSystemWalker

__all__ = [
    "FileSystemWalker",
    "FileThumbnailStore",
    "ShelfMetadataReader",
    "SqliteShelfIndex",
]
