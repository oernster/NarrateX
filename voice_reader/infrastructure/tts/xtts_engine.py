"""Coqui XTTS adapter.

This module is intentionally lazy-loading to avoid heavy initialization in tests.
"""

from __future__ import annotations

import inspect
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voice_reader.domain.entities.voice_profile import VoiceProfile
from voice_reader.domain.interfaces.tts_engine import TTSEngine
from voice_reader.shared.errors import TTSError


@dataclass
class XTTSCoquiEngine(TTSEngine):
    model_name: str
    max_reference_seconds: float = 20.0
    reference_sample_rate: int = 22_050
    max_reference_files: int = 3

    # Heuristics to automatically pick a "good" window from a long reference.
    # These are intentionally simple and dependency-light (no VAD model).
    rms_window_ms: int = 50
    silence_rms_ratio: float = 0.02

    def __post_init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._tts: Any | None = None
        self._gpu: bool | None = None

    @property
    def engine_name(self) -> str:
        return "Coqui XTTS"

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
        device: str,
        language: str,
    ) -> Path:
        try:
            t0_all = None
            try:
                import time

                t0_all = time.perf_counter()
            except Exception:
                t0_all = None

            speaker_wav = [str(p) for p in voice_profile.reference_audio_paths]
            if not speaker_wav:
                raise TTSError(
                    "XTTS requires reference audio samples. Add WAVs under "
                    "voices/<voice_name>/*.wav"
                )

            # Work around torchaudio's optional TorchCodec/FFmpeg dependency on
            # Windows. XTTS uses torchaudio.load() internally for speaker WAVs.
            # If TorchCodec isn't available/working, pre-load and re-save the
            # reference audio using soundfile so torchaudio doesn't need
            # TorchCodec.
            speaker_wav = [
                str(self._ensure_torchaudio_loadable_wav(Path(p))) for p in speaker_wav
            ]

            # Using too many reference clips can degrade quality (and increases
            # conditioning time). Cap it deterministically.
            if self.max_reference_files > 0:
                speaker_wav = speaker_wav[: self.max_reference_files]
            self._log.debug(
                "XTTS synthesize: speaker_wav=%s",
                [Path(p).name for p in speaker_wav],
            )

            # Only initialize the heavy model after validating inputs.
            tts = self._get_or_create(device=device)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # XTTS generation is sampling-based and can vary noticeably across
            # chunks/runs. Set a stable seed so voice/prosody doesn't “wander”
            # when cache is cleared or when re-synthesizing.
            self._apply_deterministic_seed(text=text, voice_profile=voice_profile)

            # torchaudio 2.10 on Windows routes `torchaudio.load()` through
            # TorchCodec (and therefore FFmpeg DLLs). XTTS uses `torchaudio.load`
            # internally for speaker WAVs; we only need basic WAV decoding.
            #
            # Patch `torchaudio.load` to use `soundfile`.
            original_torchaudio_load = None
            try:  # pragma: no cover
                import numpy as np
                import soundfile as sf
                import torch
                import torchaudio

                original_torchaudio_load = torchaudio.load

                def _load_via_soundfile(audiopath, *args, **kwargs):
                    del args, kwargs
                    data, sr = sf.read(str(audiopath), dtype="float32", always_2d=True)
                    # soundfile -> (frames, channels)
                    # torchaudio -> (channels, frames)
                    data = np.asarray(data, dtype=np.float32).T
                    return torch.from_numpy(data), int(sr)

                torchaudio.load = _load_via_soundfile  # type: ignore[assignment]
            except Exception:
                # Best-effort: if patching fails, XTTS may still run depending on
                # the user's torchaudio/torchcodec setup.
                original_torchaudio_load = None

            try:
                self._log.debug(
                    "XTTS tts_to_file start: text_len=%s out=%s",
                    len(text),
                    output_path.as_posix(),
                )

                # We already chunk text in-app; XTTS's internal sentence
                # splitting can introduce odd cadence and occasional repeats.
                # Prefer disabling it when supported.
                try:
                    tts.tts_to_file(
                        text=text,
                        speaker_wav=speaker_wav,
                        language=language,
                        file_path=str(output_path),
                        split_sentences=False,
                    )
                except TypeError:
                    try:
                        tts.tts_to_file(
                            text=text,
                            speaker_wav=speaker_wav,
                            language=language,
                            file_path=str(output_path),
                            enable_text_splitting=False,
                        )
                    except TypeError:
                        tts.tts_to_file(
                            text=text,
                            speaker_wav=speaker_wav,
                            language=language,
                            file_path=str(output_path),
                        )
                if t0_all is not None:
                    import time

                    self._log.debug(
                        "XTTS tts_to_file done: elapsed=%.2fs out=%s",
                        time.perf_counter() - t0_all,
                        output_path.as_posix(),
                    )
            finally:
                if original_torchaudio_load is not None:
                    try:  # pragma: no cover
                        import torchaudio

                        torchaudio.load = (
                            original_torchaudio_load  # type: ignore[assignment]
                        )
                    except Exception:
                        pass
            return output_path
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover
            raise TTSError(str(exc)) from exc

    def _ensure_torchaudio_loadable_wav(self, path: Path) -> Path:
        """Return a WAV path that torchaudio can load without TorchCodec.

        This creates a temporary PCM-16 WAV copy next to the original file if
        needed.
        """

        # If this already looks like a derived reference WAV, don't derive again.
        # Otherwise we end up with ref.ref.ref.wav explosions.
        lowered = path.name.lower()
        if lowered.endswith(".ref.wav") or ".ref.ref" in lowered:
            return path

        out = path.with_name(f"{path.stem}.ref.wav")
        try:
            if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
                return out
        except Exception:
            pass

        try:
            import numpy as np
            import soundfile as sf
            import torch
            import torchaudio

            # Read with soundfile (does not require FFmpeg/TorchCodec).
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)

            try:
                seconds = float(data.shape[0]) / float(sr)
                self._log.debug(
                    "XTTS ref preprocess: in=%s sr=%s seconds=%.2f",
                    path.name,
                    int(sr),
                    seconds,
                )
            except Exception:
                pass

            # Downmix to mono.
            if data.shape[1] > 1:
                data = data.mean(axis=1, keepdims=True)

            # Auto-pick a high-energy window from long files and avoid leading
            # silence/breaths where possible.
            # data is (frames, 1)
            data = self._select_reference_window(
                data=data,
                sample_rate=int(sr),
                max_seconds=float(self.max_reference_seconds),
            )

            # Convert to torch (channels, frames).
            wav = torch.from_numpy(np.asarray(data, dtype=np.float32).T)

            # Resample to a stable SR.
            if int(sr) != int(self.reference_sample_rate):
                wav = torchaudio.functional.resample(
                    wav, int(sr), int(self.reference_sample_rate)
                )

            # Trim to speed up conditioning (XTTS speaker embedding extraction).
            max_frames = int(self.max_reference_seconds * self.reference_sample_rate)
            if wav.shape[1] > max_frames:
                wav = wav[:, :max_frames]

            # Write back as PCM16 mono WAV (frames, channels).
            out.parent.mkdir(parents=True, exist_ok=True)
            sf.write(
                str(out),
                wav.squeeze(0).cpu().numpy(),
                int(self.reference_sample_rate),
                subtype="PCM_16",
            )

            try:
                trimmed_seconds = float(wav.shape[1]) / float(self.reference_sample_rate)
                self._log.debug(
                    "XTTS ref preprocess: out=%s sr=%s seconds=%.2f",
                    out.name,
                    int(self.reference_sample_rate),
                    trimmed_seconds,
                )
            except Exception:
                pass
            return out
        except Exception:
            # If preprocessing fails for any reason, fall back to the original.
            return path

    def _select_reference_window(
        self,
        *,
        data: "Any",
        sample_rate: int,
        max_seconds: float,
    ) -> "Any":
        """Pick a representative window from a long reference clip.

        Goal:
        - avoid long initial silence / mouth noises
        - avoid conditioning on quiet segments

        This is *not* a full VAD; it's a simple RMS-energy selector.

        Args:
            data: float32 numpy-like array shaped (frames, 1)
        """

        try:
            import numpy as np

            if data is None:
                return data
            frames = int(getattr(data, "shape", [0])[0])
            if frames <= 0 or sample_rate <= 0:
                return data

            max_frames = int(max_seconds * sample_rate)
            if frames <= max_frames:
                return data

            mono = np.asarray(data[:, 0], dtype=np.float32)
            mono = np.nan_to_num(mono)
            mono = np.clip(mono, -1.0, 1.0)

            # Optionally drop a little bit of the very start (often clicks/breath).
            drop_start_s = float(os.getenv("NARRATEX_REF_DROP_START_SECONDS", "0") or 0)
            drop_frames = int(max(0.0, drop_start_s) * sample_rate)
            if drop_frames > 0 and drop_frames < frames - 1:
                mono = mono[drop_frames:]
                frames = mono.shape[0]
                if frames <= max_frames:
                    return mono.reshape(-1, 1)

            # Compute windowed RMS.
            win = max(16, int(sample_rate * (self.rms_window_ms / 1000.0)))
            hop = win
            n = (frames - win) // hop + 1
            if n <= 1:
                return mono[:max_frames].reshape(-1, 1)

            rms = np.empty(n, dtype=np.float32)
            for i in range(n):
                s = i * hop
                chunk = mono[s : s + win]
                rms[i] = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))

            peak = float(np.max(rms)) if rms.size else 0.0
            if peak <= 0:
                return mono[:max_frames].reshape(-1, 1)

            # Trim leading/trailing near-silence based on relative threshold.
            thr = peak * float(self.silence_rms_ratio)
            active = np.where(rms > thr)[0]
            if active.size >= 2:
                first = int(active[0] * hop)
                last = int(min(frames, active[-1] * hop + win))
                mono = mono[first:last]
                frames = mono.shape[0]
                if frames <= max_frames:
                    return mono.reshape(-1, 1)

                # Recompute RMS on the trimmed signal.
                n = (frames - win) // hop + 1
                if n <= 1:
                    return mono[:max_frames].reshape(-1, 1)
                rms = np.empty(n, dtype=np.float32)
                for i in range(n):
                    s = i * hop
                    chunk = mono[s : s + win]
                    rms[i] = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))

            # Select the contiguous segment of length `max_frames` with highest
            # mean RMS.
            seg_steps = max(1, max_frames // hop)
            if seg_steps >= rms.size:
                return mono[:max_frames].reshape(-1, 1)

            # Moving average of rms.
            cumsum = np.cumsum(np.concatenate([[0.0], rms.astype(np.float64)]))
            means = (cumsum[seg_steps:] - cumsum[:-seg_steps]) / float(seg_steps)
            best_i = int(np.argmax(means)) if means.size else 0
            start = int(best_i * hop)
            end = int(min(frames, start + max_frames))
            picked = mono[start:end]
            if picked.shape[0] < max_frames:
                # Pad by taking a little earlier if needed.
                start = int(max(0, end - max_frames))
                picked = mono[start:end]
            return picked.reshape(-1, 1)
        except Exception:
            return data

    def _apply_deterministic_seed(self, *, text: str, voice_profile: VoiceProfile) -> None:
        """Best-effort determinism for XTTS sampling.

        This reduces chunk-to-chunk prosody drift and run-to-run differences,
        especially now that we can clear cache every launch.

        Control:
        - Set `NARRATEX_TTS_SEED` to an int to pin the seed (default: 0).
        - Set `NARRATEX_TTS_SEED_MODE=per_run|per_chunk` (default: per_run).
        """

        raw_seed = os.getenv("NARRATEX_TTS_SEED", "0").strip()
        try:
            base_seed = int(raw_seed)
        except Exception:
            base_seed = 0

        mode = os.getenv("NARRATEX_TTS_SEED_MODE", "per_run").strip().lower()
        seed = base_seed
        if mode == "per_chunk":
            # Deterministic, but varies between chunks.
            # Keep it stable across runs by hashing text and voice name.
            import hashlib

            h = hashlib.sha256(
                (voice_profile.name + "|" + text).encode("utf-8", errors="ignore")
            ).hexdigest()
            seed = (base_seed + int(h[:8], 16)) % (2**31 - 1)

        try:
            random.seed(seed)
        except Exception:
            pass

        try:
            import numpy as np

            np.random.seed(seed % (2**32 - 1))
        except Exception:
            pass

        try:
            import torch

            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

            # Determinism knobs (best-effort; safe on CPU and GPU).
            try:
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
            except Exception:
                pass
        except Exception:
            pass

    def _get_or_create(self, *, device: str) -> Any:
        use_gpu = device == "cuda"
        if self._tts is not None and self._gpu == use_gpu:
            return self._tts

        # Model load is expensive but not frequent; keep at INFO.
        self._log.info("Loading TTS model %s (gpu=%s)", self.model_name, use_gpu)
        torch_load_original = None
        try:

            # PyTorch >= 2.6 defaults `torch.load(weights_only=True)`, which can
            # reject globals found in Coqui XTTS checkpoints.
            #
            # When available, allowlist the XTTS config class so the checkpoint
            # can load safely (weights_only=True) without disabling the safety
            # mechanism globally.
            try:  # pragma: no cover
                import torch

                # 1) Try allowlisting a set of known XTTS-related classes.
                # (There can be more than one, depending on the model version.)
                if hasattr(torch, "serialization") and hasattr(
                    torch.serialization, "add_safe_globals"
                ):
                    try:
                        from TTS.config.shared_configs import BaseDatasetConfig
                        from TTS.tts.configs.xtts_config import XttsConfig
                        from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig

                        torch.serialization.add_safe_globals(
                            [BaseDatasetConfig, XttsConfig, XttsArgs, XttsAudioConfig]
                        )
                    except Exception:
                        pass

                # 2) Force weights_only=False when torch supports it.
                # XTTS checkpoints currently rely on full unpickling.
                try:
                    sig = inspect.signature(torch.load)
                    supports_weights_only = "weights_only" in sig.parameters
                except Exception:
                    supports_weights_only = False

                if supports_weights_only:
                    torch_load_original = torch.load

                    def _torch_load_compat(*args, **kwargs):
                        if "weights_only" not in kwargs:
                            kwargs["weights_only"] = False
                        return torch_load_original(*args, **kwargs)

                    torch.load = _torch_load_compat  # type: ignore[assignment]

            except Exception:
                # Best-effort; if allowlisting isn't available or fails, TTS
                # may still load depending on torch/TTS versions.
                pass

            from TTS.api import TTS

            self._tts = TTS(self.model_name, gpu=use_gpu)
            self._gpu = use_gpu
            return self._tts
        except Exception as exc:  # pragma: no cover
            raise TTSError(f"Failed to load TTS model: {exc}") from exc
        finally:
            # Restore torch.load if we patched it.
            try:  # pragma: no cover
                if torch_load_original is not None:
                    import torch

                    torch.load = torch_load_original  # type: ignore[assignment]
            except Exception:
                pass
