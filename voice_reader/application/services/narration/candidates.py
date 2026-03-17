from __future__ import annotations

from typing import TYPE_CHECKING

from voice_reader.application.services.narration._types import PlaybackCandidate

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.voice_profile import VoiceProfile


def build_playback_candidates(
    service: NarrationService,
    *,
    voice: VoiceProfile,
    book_id: str,
):
    candidates: list[PlaybackCandidate] = []
    for chunk in service._chunks:  # noqa: SLF001 (internal collaborator)
        mapped = service.sanitized_text_mapper.sanitize_with_mapping(
            original_text=chunk.text
        )
        speak_text = mapped.speak_text
        if not speak_text:
            continue

        path = service.cache_repo.audio_path(
            book_id=book_id,
            voice_name=voice.name,
            chunk_id=chunk.chunk_id,
        )
        candidates.append(
            PlaybackCandidate(
                chunk=chunk,
                speak_text=speak_text,
                speak_to_original=list(mapped.speak_to_original),
                audio_path=path,
            )
        )
    return candidates
