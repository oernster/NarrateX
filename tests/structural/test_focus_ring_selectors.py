"""No stylesheet paints a focus or hover ring on a pane or a region.

A ring belongs to a control. Three stylesheet shapes put one somewhere else:

- A `:focus` or `:hover` ring on a container class or `*`. A QSS class
  selector matches every subclass, so `QFrame:focus` reaches every text view,
  list and label in the app. An object name scopes the rule to one widget and
  is allowed.
- Any ring on an item view (list, table, tree), in any state. Its current item
  already shows where the reader is; a rectangle round the whole view fires on
  a click into the empty space below the items, outlining everything while
  selecting nothing.
- Any ring on a text view (the reader, a licence, the Guide), in any state,
  focus included. A text view is a pane, as in ClearBudget, AudioDeck and
  Fulcrum, none of which rings one; Tab reaching it rang the whole page green.
- A `:hover` ring on any other scrolling region. The pointer rests inside a
  region for as long as the window is open, so the ring reports where the
  mouse is rather than what is about to be pressed.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SOURCES = ("voice_reader", "installer")

CONTAINERS = frozenset(
    {
        "*",
        "QWidget",
        "QFrame",
        "QAbstractScrollArea",
        "QScrollArea",
        "QGroupBox",
        "QStackedWidget",
        "QSplitter",
        "QTabWidget",
        "QDockWidget",
        "QMdiArea",
    }
)
ITEM_VIEWS = frozenset(
    {
        "QAbstractItemView",
        "QListView",
        "QListWidget",
        "QTableView",
        "QTableWidget",
        "QTreeView",
        "QTreeWidget",
        "QColumnView",
    }
)
TEXT_VIEWS = frozenset({"QTextEdit", "QPlainTextEdit", "QTextBrowser"})
REGIONS = CONTAINERS | ITEM_VIEWS | TEXT_VIEWS

_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_DECLARATION = re.compile(r"([a-z-]+)\s*:\s*([^;]+)")
_INVISIBLE = ("none", "0", "transparent")


def _plain_qss(text: str) -> str:
    """Resolve an f-string sheet: doubled braces become braces, fields a value."""

    if "{{" not in text:
        return text
    marked = text.replace("{{", "\x01").replace("}}", "\x02")
    marked = re.sub(r"\{[^{}\x01\x02]*\}", "V", marked)
    return marked.replace("\x01", "{").replace("\x02", "}")


def _paints_a_ring(body: str) -> bool:
    for prop, value in _DECLARATION.findall(body):
        if not prop.startswith(("border", "outline")) or prop.endswith("radius"):
            continue
        if not value.strip().lower().startswith(_INVISIBLE):
            return True
    return False


def _subjects(selector_text: str):
    """(selector, subject class) for each selector in a rule's selector list."""

    for raw in selector_text.split(","):
        lines = raw.strip().splitlines()
        selector = lines[-1] if lines else ""
        for marker in ('"', "'", "="):
            selector = selector.rsplit(marker, 1)[-1]
        selector = " ".join(selector.split())
        if not selector:
            continue
        subject = re.split(r"[\s>]+", selector)[-1]
        if "::" not in subject:
            yield selector, subject


def ring_offences(text: str) -> list[str]:
    found = []
    for match in _RULE.finditer(_plain_qss(text)):
        if not _paints_a_ring(match.group(2)):
            continue
        for selector, subject in _subjects(match.group(1)):
            base = re.split(r"[:#\[.]", subject)[0]
            focus, hover = ":focus" in subject, ":hover" in subject
            if not (focus or hover):
                continue
            if base in CONTAINERS and "#" not in subject:
                found.append(f"container ring: {selector}")
            elif base in ITEM_VIEWS:
                found.append(f"item view ring: {selector}")
            elif base in TEXT_VIEWS:
                found.append(f"text view ring: {selector}")
            elif base in REGIONS and hover:
                found.append(f"region hover ring: {selector}")
    return found


def test_no_stylesheet_rings_a_pane_or_a_region() -> None:
    found = []
    for package in _SOURCES:
        for path in sorted((_ROOT / package).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(_ROOT)
            found.extend(f"{rel}: {o}" for o in ring_offences(text))
    assert found == []


def test_the_scan_catches_each_fault_and_spares_the_sanctioned_forms() -> None:
    sheet = """SHEET = f'''
        QFrame:focus {{ border: 2px solid {ring}; }}
        QListWidget:enabled:focus {{ border-color: {ring}; }}
        QTextEdit:enabled:hover, QTextEdit:enabled:focus {{
            border: 1px solid {ring};
        }}
        QPushButton:enabled:hover {{ border-color: {ring}; }}
        QScrollArea#Page:enabled:focus {{ border: 2px solid {ring}; }}
        QScrollArea#Page:enabled:hover {{ border: 2px solid {ring}; }}
        QListWidget::item:hover {{ border: 1px solid {ring}; }}
        QComboBox:enabled:focus {{ border-radius: 6px; }}
        * {{ outline: none; }}
    '''"""
    assert ring_offences(sheet) == [
        "container ring: QFrame:focus",
        "item view ring: QListWidget:enabled:focus",
        "text view ring: QTextEdit:enabled:hover",
        "text view ring: QTextEdit:enabled:focus",
        "region hover ring: QScrollArea#Page:enabled:hover",
    ]
