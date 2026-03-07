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

### Voice cloning requires Coqui `TTS` (typically Python 3.11)

Voice cloning (Coqui XTTS via the `TTS` package + `torch`) requires an
environment where `TTS` is installable (typically Python **3.11**).

This workspace is currently running Python 3.13, which cannot install Coqui
`TTS` at the time of writing.

To keep the app working end-to-end on Python 3.13, the app automatically falls
back to offline system TTS (`pyttsx3`).

Important: `pyttsx3` cannot do voice cloning. It can only select among
installed system voices. Voice samples under `voices/<voice_name>/*.wav` are
only used when the engine is **Coqui XTTS**.

### Can I use voice cloning on Python 3.13?

Not currently with the Coqui `TTS` Python package. For voice cloning in this
project, **Python 3.11 is mandatory**.

On Python 3.13, `pip` cannot install `TTS` because there is no compatible wheel
published for that Python version at the time of writing (you’ll see
"No matching distribution found for TTS" if you try).

Practical options:

1) Use a separate Python 3.11 environment for XTTS voice cloning, and run the UI
   app in that environment.
2) (More advanced) Run XTTS as a separate local service (Python 3.11) and keep
   the UI on Python 3.13; the UI would call the service over HTTP/IPC.


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

Note: the app does **not** currently scan `voices/*.wav` directly. A single file
like `voices/oliver.wav` must live under a voice folder, e.g.
`voices/oliver/oliver.wav`.

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

