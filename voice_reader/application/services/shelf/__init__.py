"""The shelf's use cases: scanning the disk; the shelf a reader looks at.

Each reader-visible action has one named entry point here, callable from a test
with no window open. That is the diagnostic the specification asks for: if an
action cannot be driven headlessly, the feature does not exist yet and the UI
is not the missing piece.
"""

from voice_reader.application.services.shelf.filling import ShelfFilling
from voice_reader.application.services.shelf.library import RootOutcome, ShelfLibrary
from voice_reader.application.services.shelf.scanning import ScanReport, ShelfScanner

__all__ = [
    "RootOutcome",
    "ScanReport",
    "ShelfFilling",
    "ShelfLibrary",
    "ShelfScanner",
]
