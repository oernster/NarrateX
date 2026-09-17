"""Help | Guide: what each control does, led by the picture it wears.

The ClearBudget pattern. One page, read top to bottom: the controls first, each
row led by the real artwork the button draws, then what no screen can say for
itself. Never an emoji, never a word standing in for a picture: a guide showing
something other than the icon is worse than none. Anything a control already
says for itself on hover is left to the control; About and the licences are not
repeated here.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from voice_reader.ui.artwork import GUIDE_ICON_PX, Artwork, artwork_path
from voice_reader.ui.auto_scroller import AutoScroller
from voice_reader.ui.first_stop_dialog import FirstStopDialog
from voice_reader.ui.pane_focus import follow_overflow
from voice_reader.version import APP_NAME

GUIDE_TITLE = "Guide"
GUIDE_MIN_WIDTH = 640
GUIDE_MIN_HEIGHT = 560

# Pictures that are not controls of their own, so the Guide does not list them:
# the pin marks a row inside a dialog; the muted speaker is the volume button
# showing its other state and is named in that button's row.
NOT_LISTED = frozenset({Artwork.PIN, Artwork.VOLUME_MUTED})


def _img(name: Artwork) -> str:
    path = artwork_path(name)
    if not path.is_file():
        return ""
    url = path.as_posix()
    return (
        f'<img src="file:///{url}" width="{GUIDE_ICON_PX}" '
        f'height="{GUIDE_ICON_PX}" style="vertical-align: middle"> '
    )


def _row(names: Artwork | tuple[Artwork, ...], label: str, text: str) -> str:
    pictures = names if isinstance(names, tuple) else (names,)
    return f"<p>{''.join(_img(n) for n in pictures)}<b>{label}</b>: {text}</p>"


def guide_html() -> str:
    return f"""
<h2>How {APP_NAME} works</h2>

<h3>Choosing what to hear</h3>
{_row(Artwork.SELECT_BOOK, "Select book", "open an EPUB, PDF, text or Markdown file.")}
{_row(Artwork.REMOVE_CURRENT_BOOK, "Remove current book",
      "forget the bookmarks, resume point, ideas map and cached audio for "
      "this book. The file on disk is never touched.")}
{_row((Artwork.FEMALE, Artwork.MALE), "Female or male",
      "press to switch which voices the list shows.")}
{_row((Artwork.UK_FLAG, Artwork.US_FLAG), "British or American",
      "press to switch accents.")}
{_row(Artwork.SELECT_VOICE, "Select voice",
      "choose the narrator. Nothing plays until one is chosen.")}
{_row(Artwork.VOLUME_CONTROL, "Volume",
      "press to mute; the speaker is crossed out while muted. Press again for "
      "the level you had. The slider beside it sets the level.")}

<h3>Playing</h3>
{_row(Artwork.PREVIOUS_CHAPTER, "Previous chapter", "jump back a chapter.")}
{_row(Artwork.PLAY, "Play", "start or carry on reading aloud.")}
{_row(Artwork.PAUSE, "Pause", "hold your place; press again to carry on.")}
{_row(Artwork.STOP, "Stop", "end playback.")}
{_row(Artwork.NEXT_CHAPTER, "Next chapter", "jump forward a chapter.")}
<p>A red ring round a chapter button means pressing it would do nothing right
now: nothing is playing or paused, no voice is chosen or there is no chapter
that way.</p>

<h3>Finding your way</h3>
{_row(Artwork.BOOKMARKS, "Bookmarks", "add, revisit or delete bookmarks.")}
{_row(Artwork.SECTIONS, "Sections", "jump to a chapter or heading of the book.")}
{_row(Artwork.HELP, "Help", "this Guide and About.")}

<h3>The strip along the foot</h3>
{_row(Artwork.DONATE, "Donate",
      f"opens a donation page in your browser. {APP_NAME} itself sends "
      "nothing; nothing is held back behind it.")}
{_row((Artwork.UI_LICENCE, Artwork.BACKEND_LICENCE), "UI and Backend licences",
      f"the two licences {APP_NAME} is under.")}

<h3>Also worth knowing</h3>
<p>Click in the text to move the reading position to that point. The passage
being read is highlighted as it is spoken; the spine to the left of the text
shows where each chapter sits in the book.</p>

<h3>Keyboard</h3>
<p><b>Tab</b> and <b>Shift+Tab</b> move between controls; <b>Left</b> and
<b>Right</b> do the same along a row of buttons. <b>Enter</b> or <b>Space</b>
presses the one ringed. <b>Down</b> opens a dropdown. On the speaker,
<b>Up</b> and <b>Down</b> change the volume. In the text, <b>Up</b> and
<b>Down</b> scroll.</p>
"""


class GuideDialog(FirstStopDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(GUIDE_TITLE)
        self.setModal(True)
        self.setMinimumSize(GUIDE_MIN_WIDTH, GUIDE_MIN_HEIGHT)

        layout = QVBoxLayout(self)
        self.body = QTextBrowser(self)
        self.body.setObjectName("GuideText")
        self.body.setOpenExternalLinks(False)
        self.body.setHtml(guide_html())
        layout.addWidget(self.body, 1)
        self.overflow_focus = follow_overflow(self.body)
        self.scroller = AutoScroller(self.body)

        row = QHBoxLayout()
        row.addStretch(1)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.accept)
        row.addWidget(self.close_button)
        layout.addLayout(row)
