# voice_reader

Local AI audiobook reader for ebooks with optional voice cloning.

## What you get

- Desktop UI (PySide6)
- Book ingestion (EPUB/PDF/TXT + Kindle formats via Calibre conversion)
- Streaming playback while generating audio
- Audio cache per book/voice/chunk
- Text highlighting per spoken chunk
- Multiple voice profiles (`voices/<voice_name>/*.wav`)

## Architecture

Clean Architecture:

- UI: [`voice_reader/ui`](voice_reader/ui:1)
- Application (orchestration): [`voice_reader/application`](voice_reader/application:1)
- Domain (entities + interfaces + services): [`voice_reader/domain`](voice_reader/domain:1)
- Infrastructure (adapters): [`voice_reader/infrastructure`](voice_reader/infrastructure:1)

Dependency direction: UI → Application → Domain, and Infrastructure implements Domain interfaces.

## Python version support (important)

Voice cloning (Coqui XTTS via `TTS` + `torch`) typically supports Python 3.11.

This workspace is currently running Python 3.13, which cannot install Coqui `TTS` at the time of writing.

To keep the app working end-to-end on Python 3.13, the app automatically falls back to offline system TTS (`pyttsx3`).

Engine selection is done by [`voice_reader.application.services.tts_engine_factory.TTSEngineFactory`](voice_reader/application/services/tts_engine_factory.py:1).

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Calibre (Kindle conversion)

Kindle formats are converted using Calibre `ebook-convert`:

1. Install Calibre: https://calibre-ebook.com/download
2. Ensure `ebook-convert` is on PATH

## Voice samples (for XTTS voice cloning)

Place WAV samples here:

```
voices/<voice_name>/*.wav
```

Multiple samples are supported.

On Python 3.13 fallback TTS (`pyttsx3`) is used; it selects a system voice by (best-effort) name match and does not use these WAV samples.

## Run

```powershell
python app.py
```

## Tests

```powershell
python -m pytest
```

## CPU/GPU selection

Device selection is automatic in [`voice_reader.application.services.device_detection_service.DeviceDetectionService`](voice_reader/application/services/device_detection_service.py:1):

- `cuda` if `torch.cuda.is_available()`
- otherwise `cpu`

CPU always works.

