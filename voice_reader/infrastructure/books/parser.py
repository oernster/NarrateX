"""Book parsing for EPUB/PDF/TXT."""

from __future__ import annotations

import logging
import warnings
import re
from dataclasses import dataclass
from pathlib import Path
from voice_reader.shared.errors import BookParseError

log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\u00A0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass(frozen=True, slots=True)
class BookParser:
    def parse(self, path: Path) -> tuple[str, str]:
        ext = path.suffix.lower()
        if ext == ".txt":
            raw = path.read_text(encoding="utf-8", errors="ignore")
            return raw, normalize_text(raw)
        if ext == ".pdf":
            return self._parse_pdf(path)
        if ext == ".epub":
            return self._parse_epub(path)
        raise BookParseError(f"Unsupported parse format: {ext}")

    def _parse_pdf(self, path: Path) -> tuple[str, str]:
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(path))
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text("text"))
            raw = "\n\n".join(pages)
            return raw, normalize_text(raw)
        except Exception as exc:
            raise BookParseError(str(exc)) from exc

    def _parse_epub(self, path: Path) -> tuple[str, str]:
        try:
            import ebooklib
            from ebooklib import epub

            def _read_epub(*, ignore_ncx: bool) -> object:
                # EbookLib defaults `ignore_ncx=True`.
                # Some real-world EPUB3 files (including KDP-valid exports) have a
                # nav doc that triggers an IndexError in EbookLib's `_parse_nav()`.
                # In those cases, allowing NCX parsing fixes loading.
                return epub.read_epub(
                    str(path),
                    options={"ignore_ncx": bool(ignore_ncx)},
                )

            try:
                book = _read_epub(ignore_ncx=True)
            except Exception as exc:
                # Expected fallback for some real-world EPUB3/KDP files:
                # EbookLib can raise in nav parsing with ignore_ncx=True.
                # Keep the console clean (no full traceback) unless DEBUG is enabled.
                log.warning(
                    "EPUB read failed (ignore_ncx=True); retrying with ignore_ncx=False: %s (%s)",
                    path,
                    exc,
                    exc_info=log.isEnabledFor(logging.DEBUG),
                )
                book = _read_epub(ignore_ncx=False)

            # Prefer reading order (spine) when available.
            items: list[object] = []
            spine = getattr(book, "spine", None) or []
            if spine:
                get_item_with_id = getattr(book, "get_item_with_id", None)
                if callable(get_item_with_id):
                    for entry in spine:
                        # EbookLib spine entries are typically (idref, linear).
                        if isinstance(entry, tuple) and entry:
                            item_id = entry[0]
                        else:
                            item_id = entry
                        if not item_id:
                            continue
                        if str(item_id).lower() in {"nav", "cover"}:
                            continue
                        it = get_item_with_id(item_id)
                        if it is None:
                            continue
                        try:
                            if getattr(it, "get_type", None) and it.get_type() != ebooklib.ITEM_DOCUMENT:
                                continue
                        except Exception:
                            pass
                        items.append(it)

            if not items:
                # Fallback: manifest document items.
                get_items_of_type = getattr(book, "get_items_of_type", None)
                if callable(get_items_of_type):
                    items = list(get_items_of_type(ebooklib.ITEM_DOCUMENT))

            # Last-resort: some malformed EPUBs have HTML/XHTML not declared as
            # ITEM_DOCUMENT. Scan by extension.
            if not items:
                get_items = getattr(book, "get_items", None)
                if callable(get_items):
                    for it in list(get_items()):
                        name = (
                            getattr(it, "file_name", None)
                            or getattr(it, "get_name", lambda: "")()
                            or ""
                        )
                        if str(name).lower().endswith((".xhtml", ".html", ".htm")):
                            items.append(it)

            log.debug(
                "EPUB parse: path=%s spine_len=%s doc_items=%s",
                path,
                len(spine) if spine is not None else 0,
                len(items),
            )

            texts: list[str] = []
            for item in items:
                html_bytes = None
                try:
                    get_content = getattr(item, "get_content", None)
                    if callable(get_content):
                        html_bytes = get_content()
                except Exception:
                    html_bytes = None
                if not html_bytes:
                    try:
                        get_body_content = getattr(item, "get_body_content", None)
                        if callable(get_body_content):
                            html_bytes = get_body_content()
                    except Exception:
                        html_bytes = None
                if not html_bytes:
                    continue

                text = _html_to_text(html_bytes)
                if text:
                    texts.append(text)

            raw = "\n\n".join(texts)
            norm = normalize_text(raw)
            log.debug(
                "EPUB parse done: path=%s raw_len=%s norm_len=%s",
                path,
                len(raw),
                len(norm),
            )
            return raw, norm
        except Exception as exc:
            raise BookParseError(str(exc)) from exc


def _html_to_text(html_bytes: bytes) -> str:
    """Best-effort HTML/XHTML -> text while preserving rough block boundaries."""

    # Preferred path: BeautifulSoup preserves separators well.
    try:
        from bs4 import BeautifulSoup
        from bs4 import XMLParsedAsHTMLWarning

        # Many EPUB documents are XHTML. When parsing with the HTML parser (or
        # BeautifulSoup+lxml) BeautifulSoup may emit XMLParsedAsHTMLWarning.
        # This is expected in our use-case and becomes noisy in user logs.
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

        try:
            soup = BeautifulSoup(html_bytes, "lxml")
        except Exception:
            soup = BeautifulSoup(html_bytes, "html.parser")
        return (soup.get_text("\n", strip=True) or "").strip()
    except Exception:
        pass

    # Fallback: lxml.html
    try:
        from lxml import etree, html

        doc = html.fromstring(html_bytes)
        # Insert newlines after common block elements.
        block_xpath = "//p|//div|//section|//article|//li|//h1|//h2|//h3|//h4|//h5|//h6|//br"
        for el in doc.xpath(block_xpath):
            try:
                if el.tag.lower() == "br":
                    el.tail = ("\n" + (el.tail or ""))
                else:
                    el.tail = ("\n\n" + (el.tail or ""))
            except Exception:
                continue
        text = (doc.text_content() or "").strip()
        # Defensive: collapse huge whitespace; downstream normalizer will do more.
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
    except Exception:
        pass

    # Last-resort: strip tags crudely.
    try:
        s = html_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</p\s*>", "\n\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()
