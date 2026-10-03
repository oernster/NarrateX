"""Whether an EPUB that yielded no text is copy protected.

Asked only after a book parses to nothing, to choose the reason the reader is
given. An EPUB lists what it encrypts in `META-INF/encryption.xml`. Font
obfuscation uses the same file in books with no protection at all, so an entry
counts as protection only when its algorithm is not one of the two font
obfuscation schemes. Notes that cannot be read at all count as protection: a
book with no text and encryption notes nobody can read is far likelier locked
than scanned.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

_ENCRYPTION_NOTES = "META-INF/encryption.xml"

# The IDPF and Adobe font obfuscation algorithms: these hide a font's bytes
# from casual copying and leave the book's text in the clear.
_FONT_OBFUSCATION = frozenset(
    {
        "http://www.idpf.org/2008/embedding",
        "http://ns.adobe.com/pdf/enc#RC",
    }
)

_XMLENC = "{http://www.w3.org/2001/04/xmlenc#}"

# Encryption notes hold one short entry per encrypted file. The bound is
# generous for that and stops a hostile archive's notes being inflated whole.
MAX_NOTES_BYTES = 1024 * 1024


def is_protected(path: Path) -> bool:
    """True when this file's encryption notes encrypt more than fonts."""

    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(_ENCRYPTION_NOTES)
            if info.file_size > MAX_NOTES_BYTES:
                return True
            notes = archive.read(info)
    except (KeyError, OSError, zipfile.BadZipFile):
        return False
    try:
        root = ElementTree.fromstring(notes)
    except ElementTree.ParseError:
        return True
    algorithms = [
        method.get("Algorithm", "")
        for method in root.iter(f"{_XMLENC}EncryptionMethod")
    ]
    return any(algorithm not in _FONT_OBFUSCATION for algorithm in algorithms)
