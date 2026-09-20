"""Reading an EPUB's documents; dropping what is not the book.

Split from `parser` so that module stays inside the size limit; these three
answer one question between them, which is what a document actually contains.
"""

from __future__ import annotations

from collections.abc import Sequence

from voice_reader.domain.document import running_headers
from voice_reader.domain.document.anchoring import BlockDraft


def item_html(item) -> bytes | None:
    """The bytes of one EPUB document, however the reader chooses to give them."""

    for name in ("get_content", "get_body_content"):
        try:
            getter = getattr(item, name, None)
            if callable(getter):
                content = getter()
                if content:
                    return content
        except Exception:
            continue
    return None


def epub_title(book) -> str | None:
    """The title the book states about itself; None where it states none."""

    try:
        stated = book.get_metadata("DC", "title")
    except Exception:
        return None
    for entry in stated or ():
        value = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def without_page_furniture(
    documents: Sequence[tuple[str, tuple[BlockDraft, ...]]],
    *,
    title: str | None,
) -> tuple[list[str], list[BlockDraft]]:
    """Drop the running header a Kindle conversion left in the body text.

    The header cannot be recognised from one document, which is why this reads
    the whole spine at once; `running_headers` holds what makes a repeated line
    furniture rather than prose.
    """

    leads = [drafts[0].text for _, drafts in documents if drafts]
    header = running_headers.running_header(leads, title=title)

    texts: list[str] = []
    kept: list[BlockDraft] = []
    for text, drafts in documents:
        lines = running_headers.without_header(text.split("\n"), header=header)
        joined = "\n".join(lines).strip()
        if joined:
            texts.append(joined)
        kept.extend(d for d in drafts if header is None or d.text.strip() != header)
    return texts, kept
