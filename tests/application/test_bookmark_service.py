from __future__ import annotations

from dataclasses import dataclass

from voice_reader.application.services.bookmark_service import BookmarkService


@dataclass
class FakeRepo:
    list_calls: int = 0
    add_calls: int = 0
    delete_calls: int = 0
    load_resume_calls: int = 0
    save_resume_calls: int = 0

    def list_bookmarks(self, *, book_id: str):
        self.list_calls += 1
        assert book_id == "b1"
        return []

    def add_bookmark(self, *, book_id: str, char_offset: int, chunk_index: int):
        self.add_calls += 1
        assert book_id == "b1"
        assert char_offset == 10
        assert chunk_index == 2
        return "bookmark"  # type: ignore[return-value]

    def delete_bookmark(self, *, book_id: str, bookmark_id: int):
        self.delete_calls += 1
        assert book_id == "b1"
        assert bookmark_id == 123

    def load_resume_position(self, *, book_id: str):
        self.load_resume_calls += 1
        assert book_id == "b1"
        return None

    def save_resume_position(self, *, book_id: str, char_offset: int, chunk_index: int):
        self.save_resume_calls += 1
        assert book_id == "b1"
        assert char_offset == 11
        assert chunk_index == 3


def test_bookmark_service_delegates_to_repo() -> None:
    repo = FakeRepo()
    svc = BookmarkService(repo=repo)  # type: ignore[arg-type]

    assert svc.list_bookmarks(book_id="b1") == []
    assert repo.list_calls == 1

    assert svc.add_bookmark(book_id="b1", char_offset=10, chunk_index=2) == "bookmark"
    assert repo.add_calls == 1

    svc.delete_bookmark(book_id="b1", bookmark_id=123)
    assert repo.delete_calls == 1

    assert svc.load_resume_position(book_id="b1") is None
    assert repo.load_resume_calls == 1

    svc.save_resume_position(book_id="b1", char_offset=11, chunk_index=3)
    assert repo.save_resume_calls == 1
