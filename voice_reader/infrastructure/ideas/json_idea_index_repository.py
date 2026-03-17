"""JSON-backed Ideas index persistence.

File format per book is defined by the Ideas data model design docs.

This repository is intentionally tolerant:

- Missing file => None
- Invalid JSON => None
- Non-dict JSON => None

Writes are atomic via write-to-temp then replace.

Persistence location decision (approved): store next to bookmarks, e.g.
`bookmarks/<book_id>.ideas.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voice_reader.domain.interfaces.idea_index_repository import IdeaIndexRepository


@dataclass(frozen=True, slots=True)
class JSONIdeaIndexRepository(IdeaIndexRepository):
    bookmarks_dir: Path

    def _path_for(self, *, book_id: str) -> Path:
        safe = str(book_id).strip()
        return self.bookmarks_dir / f"{safe}.ideas.json"

    def load_doc(self, *, book_id: str) -> dict | None:
        path = self._path_for(book_id=book_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else None
        except Exception:  # noqa: BLE001
            return None
        return data if isinstance(data, dict) else None

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        if not isinstance(doc, dict):
            raise TypeError("Idea index doc must be a dict")

        self.bookmarks_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(book_id=book_id)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=False), encoding="utf-8")
        tmp.replace(path)
