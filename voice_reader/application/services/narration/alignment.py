from __future__ import annotations

from typing import TYPE_CHECKING

from voice_reader.domain.alignment.model import ChunkAlignment, TimedTextSpan

if TYPE_CHECKING:  # pragma: no cover
    from voice_reader.application.services.narration_service import NarrationService
    from voice_reader.domain.entities.text_chunk import TextChunk
    from voice_reader.domain.entities.voice_profile import VoiceProfile


def resolve_audible_span(
    service: NarrationService,
    *,
    chunk: TextChunk,
    play_index: int,
    chunk_local_ms: int,
    playback_text_maps: list[tuple[str, list[int]]],
    book_id: str,
    voice: VoiceProfile,
) -> tuple[int | None, int | None]:
    align = None
    try:
        chunk_id = int(chunk.chunk_id)
        ap = service.cache_repo.alignment_path(
            book_id=book_id,
            voice_name=voice.name,
            chunk_id=chunk_id,
        )
        align = service.alignment_io.load(ap) if ap.exists() else None
    except Exception:
        align = None

    if align is None:
        try:
            speak_text, speak_to_orig = playback_text_maps[int(play_index)]
        except Exception:
            speak_text, speak_to_orig = "", []

        duration_ms = 0
        try:
            import soundfile as sf

            wav_path = service.cache_repo.audio_path(
                book_id=book_id,
                voice_name=voice.name,
                chunk_id=int(chunk.chunk_id),
            )
            with sf.SoundFile(str(wav_path)) as f:
                duration_ms = int(round((len(f) / float(f.samplerate)) * 1000.0))
        except Exception:
            duration_ms = max(int(chunk_local_ms), 1)

        est = service.estimated_aligner.estimate(
            chunk_id=int(chunk.chunk_id),
            speak_text=speak_text,
            speak_to_original=speak_to_orig,
            duration_ms=int(duration_ms),
        )
        spans: list[TimedTextSpan] = []
        for s in est.spans:
            spans.append(
                TimedTextSpan(
                    start_char=int(chunk.start_char) + int(s.start_char),
                    end_char=int(chunk.start_char) + int(s.end_char),
                    audio_start_ms=int(s.audio_start_ms),
                    audio_end_ms=int(s.audio_end_ms),
                    confidence=float(s.confidence),
                )
            )
        align = ChunkAlignment(
            chunk_id=int(chunk.chunk_id),
            duration_ms=int(est.duration_ms),
            spans=spans,
        )

        try:
            ap = service.cache_repo.alignment_path(
                book_id=book_id,
                voice_name=voice.name,
                chunk_id=int(chunk.chunk_id),
            )
            service.alignment_io.save(path=ap, alignment=align)
        except Exception:
            pass

    return service.playback_synchronizer.resolve_span(
        alignment=align,
        chunk_local_ms=int(chunk_local_ms),
    )
