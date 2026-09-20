"""Reducing a cover to the small copy the grid draws.

Qt does the decode, the scale and the encode. It is the only image library the
application already carries; `QImage` needs no `QApplication`, measured on
2026-09-20, decode, scale and PNG encode all work in a bare interpreter, which is
what lets this sit in infrastructure rather than in the window.

PNG rather than JPEG, because cover art holds flat colour and lettering that JPEG
smears; also because a PNG needs no quality figure to be chosen and defended.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QImage

_FORMAT = "PNG"


@dataclass(frozen=True, slots=True)
class QtThumbnailMaker:
    """Reduces an encoded image to fit a box, keeping its proportions."""

    def downscale(self, image: bytes, *, width: int, height: int) -> bytes | None:
        picture = QImage.fromData(QByteArray(image))
        if picture.isNull():
            return None
        # Only ever reduced. Enlarging a small cover to the box would trade a
        # sharp little picture for a soft big one.
        if picture.width() > width or picture.height() > height:
            picture = picture.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        if not picture.save(buffer, _FORMAT):
            return None
        return bytes(buffer.data())
