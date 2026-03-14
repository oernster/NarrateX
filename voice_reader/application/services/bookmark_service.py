"""Application service for bookmark operations.

This service is intentionally thin: persistence rules (ID allocation and
never-reuse) live in the repository. The service provides a stable entry point
for UI/application code.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.entities.bookmark import Bookmark, ResumePosition
from voice_reader.domain.interfaces.bookmark_repository import BookmarkRepository


@dataclass(frozen=True, slots=True)
class BookmarkService:
    repo: BookmarkRepository

    def list_bookmarks(self, *, book_id: str) -> list[Bookmark]:
        return self.repo.list_bookmarks(book_id=book_id)

    def add_bookmark(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> Bookmark:
        return self.repo.add_bookmark(
            book_id=book_id,
            char_offset=char_offset,
            chunk_index=chunk_index,
        )

    def delete_bookmark(self, *, book_id: str, bookmark_id: int) -> None:
        self.repo.delete_bookmark(book_id=book_id, bookmark_id=bookmark_id)

    def save_resume_position(
        self,
        *,
        book_id: str,
        char_offset: int,
        chunk_index: int,
    ) -> None:
        self.repo.save_resume_position(
            book_id=book_id,
            char_offset=char_offset,
            chunk_index=chunk_index,
        )

    def load_resume_position(self, *, book_id: str) -> ResumePosition | None:
        return self.repo.load_resume_position(book_id=book_id)
