"""Book parsing for EPUB/PDF/TXT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from voice_reader.shared.errors import BookParseError


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
            from bs4 import BeautifulSoup
            from ebooklib import epub

            book = epub.read_epub(str(path))
            items = list(book.get_items_of_type(9))  # ITEM_DOCUMENT
            texts: list[str] = []
            for item in items:
                soup = BeautifulSoup(item.get_body_content(), "html.parser")
                # Preserve headings/paragraph boundaries for downstream logic.
                texts.append(soup.get_text("\n", strip=True))
            raw = "\n\n".join(texts)
            return raw, normalize_text(raw)
        except Exception as exc:
            raise BookParseError(str(exc)) from exc
