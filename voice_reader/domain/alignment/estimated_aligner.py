"""Estimated alignment generator.

Given:
- sanitized speak_text (what was sent to TTS)
- a per-character speak->original mapping (chunk-local indices)
- WAV duration in ms

Produce spans covering contiguous regions of the original chunk text with
estimated audio timing.

This is a fallback alignment when backend timing metadata is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_reader.domain.alignment.model import ChunkAlignment, TimedTextSpan


_TOKEN_RE = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class EstimatedAligner:
    # Punctuation pause weights in "extra characters".
    comma_pause: float = 2.5
    sentence_pause: float = 6.0
    clause_pause: float = 3.5

    def estimate(
        self,
        *,
        chunk_id: int,
        speak_text: str,
        speak_to_original: list[int],
        duration_ms: int,
    ) -> ChunkAlignment:
        speak_text = (speak_text or "").strip()
        duration_ms = max(0, int(duration_ms))

        if not speak_text or duration_ms <= 0:
            return ChunkAlignment(chunk_id=int(chunk_id), duration_ms=duration_ms, spans=[])

        # Tokenize as non-whitespace runs.
        matches = list(_TOKEN_RE.finditer(speak_text))
        if not matches:
            return ChunkAlignment(chunk_id=int(chunk_id), duration_ms=duration_ms, spans=[])

        # Compute token weights.
        weights: list[float] = []
        for m in matches:
            tok = m.group(0)
            w = float(len(tok))

            # Add pause weighting based on trailing punctuation.
            tail = tok[-1:]
            if tail in {".", "!", "?"}:
                w += float(self.sentence_pause)
            elif tail in {",", ";"}:
                w += float(self.comma_pause)
            elif tail in {":", "—", "-"}:
                w += float(self.clause_pause)

            weights.append(max(w, 1.0))

        total_w = sum(weights) or 1.0

        # Allocate ms per token proportionally.
        spans: list[TimedTextSpan] = []
        t_ms = 0
        for idx, m in enumerate(matches):
            start_i = int(m.start())
            end_i = int(m.end())

            # Map speak indices to chunk-local original indices.
            # We use the first and last mapped char; if mapping is missing for
            # end_i-1 (shouldn't happen), clamp.
            if not speak_to_original:
                continue
            if start_i >= len(speak_to_original):
                continue
            end_map_idx = min(max(end_i - 1, 0), len(speak_to_original) - 1)
            o_start = int(speak_to_original[start_i])
            o_end = int(speak_to_original[end_map_idx]) + 1
            if o_end < o_start:
                o_start, o_end = o_end, o_start

            tok_ms = int(round((weights[idx] / total_w) * duration_ms))
            # Ensure monotonicity and at least 1ms when possible.
            tok_ms = max(1, tok_ms)
            start_ms = t_ms
            end_ms = min(duration_ms, t_ms + tok_ms)
            t_ms = end_ms

            if o_start == o_end:
                continue
            spans.append(
                TimedTextSpan(
                    start_char=o_start,
                    end_char=o_end,
                    audio_start_ms=start_ms,
                    audio_end_ms=end_ms,
                    confidence=0.35,
                )
            )

        # Fix last span to end at duration.
        if spans:
            last = spans[-1]
            if last.audio_end_ms != duration_ms:
                spans[-1] = TimedTextSpan(
                    start_char=last.start_char,
                    end_char=last.end_char,
                    audio_start_ms=last.audio_start_ms,
                    audio_end_ms=duration_ms,
                    confidence=last.confidence,
                )

        return ChunkAlignment(chunk_id=int(chunk_id), duration_ms=duration_ms, spans=spans)

