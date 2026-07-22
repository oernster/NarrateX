from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from voice_reader.infrastructure.cache.filesystem_cache import FilesystemCacheRepository


def test_filesystem_cache_path_and_exists(tmp_path: Path) -> None:
    repo = FilesystemCacheRepository(cache_dir=tmp_path)
    p = repo.audio_path(book_id="b", voice_name="v", chunk_id=12)
    assert p.as_posix().endswith("/b/v/000012.wav")
    assert not repo.exists(book_id="b", voice_name="v", chunk_id=12)
    repo.ensure_parent_dir(p)
    data = np.zeros(16000, dtype=np.float32)
    sf.write(str(p), data, 16000)
    assert repo.exists(book_id="b", voice_name="v", chunk_id=12)


def test_purge_book_removes_only_that_book(tmp_path: Path) -> None:
    repo = FilesystemCacheRepository(cache_dir=tmp_path)
    mine = repo.audio_path(book_id="gone", voice_name="v", chunk_id=1)
    other = repo.audio_path(book_id="kept", voice_name="v", chunk_id=1)
    for p in (mine, other):
        repo.ensure_parent_dir(p)
        p.write_bytes(b"wav")

    repo.purge_book(book_id="gone")

    assert not (tmp_path / "gone").exists()
    assert other.exists()


def test_purge_book_tolerates_a_missing_tree(tmp_path: Path) -> None:
    repo = FilesystemCacheRepository(cache_dir=tmp_path)

    repo.purge_book(book_id="never-cached")

    assert not (tmp_path / "never-cached").exists()
