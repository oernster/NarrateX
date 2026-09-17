"""The button artwork: one name per picture, where it ships and how big it draws.

Qt-free on purpose. `generate_icons.py` reads the sizes from here, so the size a
picture is rendered at and the size a button draws it at have one home and
cannot drift apart. The Qt half (turning a name into a button) lives in
`voice_reader/ui/_icon_buttons.py`.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

# The reduced copies `generate_icons.py` writes from `assets/`. Beside this
# module so every packaging route finds them the way it finds the package.
ARTWORK_DIR = Path(__file__).resolve().parent / "artwork"
ARTWORK_SUFFIX = ".png"


class Artwork(str, Enum):
    """Each value is the file stem shared by the master and its shipped copy."""

    BACKEND_LICENCE = "backend-licence"
    BOOKMARKS = "bookmarks"
    DONATE = "donate"
    FEMALE = "female"
    HELP = "help"
    MALE = "male"
    NEXT_CHAPTER = "next-chapter"
    PAUSE = "pause"
    PIN = "pin"
    PLAY = "play"
    PREVIOUS_CHAPTER = "previous-chapter"
    REMOVE_CURRENT_BOOK = "remove-current-book"
    SECTIONS = "sections"
    SELECT_BOOK = "select-book"
    SELECT_VOICE = "select-voice"
    STOP = "stop"
    UI_LICENCE = "ui-licence"
    UK_FLAG = "uk-flag"
    US_FLAG = "us-flag"
    VOLUME_CONTROL = "volume-control"
    VOLUME_MUTED = "volume-muted"


def artwork_path(name: Artwork) -> Path:
    return ARTWORK_DIR / f"{name.value}{ARTWORK_SUFFIX}"


# Every picture button in the window, top rows and foot strip alike, is a
# square of this side drawing its artwork at ICON_PX inside the interaction
# ring. The dropdowns take the same height so the controls row stays level.
ICON_BUTTON_PX = 63
ICON_PX = 48

# A list row's picture (the Bookmarks and Sections dialogs).
LIST_ROW_ICON_PX = 20

# A shipped copy holds this many pixels per drawn pixel, so the artwork stays
# crisp on a display scaled up to that factor.
RENDER_SCALE = 4

# The longest side of a shipped copy: enough for the largest drawn size.
ARTWORK_MAX_SIDE = ICON_PX * RENDER_SCALE

# The donate mark is wide rather than square, so it is rendered by height
# alone; the site's copy is the same render.
DONATE_RENDER_HEIGHT = ICON_PX * RENDER_SCALE
