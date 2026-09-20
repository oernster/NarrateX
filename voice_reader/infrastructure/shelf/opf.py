"""Reading a Calibre `metadata.opf` sitting beside a book.

FR-BS-020: the sidecar outranks the file's own metadata, because Calibre's copy
is the one a reader has curated. Measured on 2026-09-19, 652 of the reference
library's files carry one and 381 of those state at least one subject.

A file that will not parse states nothing, which the caller treats as silence
rather than as a fault.

**The sidecar is not asked about the cover.** Measured on 2026-09-19 over the
reference library: all 652 sidecars carry the OPF namespace and not one of them
names a cover, while 541 book files have a cover image sitting beside them. The
image is the mechanism, so that is what is looked for; reading a field nothing
writes would be code with no caller and no evidence behind it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

# Dublin Core, as every `.opf` in the reference library spells it.
_DC = "{http://purl.org/dc/elements/1.1/}"
_OPF = "{http://www.idpf.org/2007/opf}"

OPF_NAMES = ("metadata.opf",)

# A sidecar larger than this is not metadata. The largest in the reference
# library is a few kilobytes.
_MAX_OPF_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class OpfMetadata:
    """What one sidecar stated."""

    title: str = ""
    author: str = ""
    subjects: tuple[str, ...] = field(default_factory=tuple)


def sidecar_path(book: Path) -> Path | None:
    """The `metadata.opf` beside this book; None when there is none."""

    for name in OPF_NAMES:
        candidate = book.parent / name
        if candidate.is_file():
            return candidate
    return None


def _creator(root: ElementTree.Element) -> str:
    """The first author, preferring one marked as the author role."""

    creators = root.iter(f"{_DC}creator")
    fallback = ""
    for element in creators:
        text = (element.text or "").strip()
        if not text:
            continue
        if element.get(f"{_OPF}role") == "aut":
            return text
        fallback = fallback or text
    return fallback


def read(path: Path) -> OpfMetadata:
    """What this sidecar states; nothing at all when it cannot be read."""

    try:
        if path.stat().st_size > _MAX_OPF_BYTES:
            return OpfMetadata()
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return OpfMetadata()

    parser = ElementTree.XMLParser()
    try:
        root = ElementTree.fromstring(text, parser=parser)
    except ElementTree.ParseError:
        return OpfMetadata()

    subjects = tuple(
        (element.text or "").strip()
        for element in root.iter(f"{_DC}subject")
        if (element.text or "").strip()
    )
    title_element = next(iter(root.iter(f"{_DC}title")), None)
    title = (title_element.text or "").strip() if title_element is not None else ""

    return OpfMetadata(title=title, author=_creator(root), subjects=subjects)
