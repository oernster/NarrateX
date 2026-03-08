# voice_reader

Desktop eBook voice reader built on the Kokoro TTS library: select from multiple machine voices, load a book, and control playback (play/pause/stop) while it reads.

Where available, the UI also displays the book cover and other metadata during book handling.

For a codebase overview (layers, runtime flow, and test mapping), see [`ARCHITECTURE.md`](ARCHITECTURE.md:1).

## Supported book formats

Native:

- EPUB (`.epub`)
- PDF (`.pdf`)
- Plain text (`.txt`)

Kindle formats (via optional Calibre conversion to EPUB):

- MOBI (`.mobi`)
- AZW (`.azw`)
- AZW3 (`.azw3`)
- PRC (`.prc`)
- KFX (`.kfx`)

## Requirements

- Python 3.11

Optional:

- Calibre (for converting Kindle formats using `ebook-convert`)

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

## Build (Windows, one-file EXE via Nuitka)

This project is compatible with a Nuitka onefile build. Two separate icon
surfaces are involved:

- The **EXE/Explorer icon** (controlled by Nuitka, uses the `.ico` embedded into the EXE)
- The **runtime window/taskbar icon** (controlled by Qt at runtime; we load [`narratex.ico`](narratex.ico:1))

Suggested build command (run in an activated venv):

```powershell
python -m pip install -U nuitka

python -m nuitka `
  --onefile `
  --enable-plugin=pyside6 `
  --windows-icon-from-ico=narratex.ico `
  --include-data-file=narratex.ico=narratex.ico `
  --windows-company-name="Oliver Ernster" `
  --windows-product-name="NarrateX" `
  --windows-file-version=1.0.1 `
  --windows-product-version=1.0.1 `
  --output-filename=NarrateX.exe `
  app.py
```

Notes:

- When bundled, NarrateX writes user data (voices, temp conversions, cache) to per-user
  directories rather than the app folder. You can force this behavior in dev with
  `NARRATEX_USER_DIRS=1`.

### Voices in onefile builds

NarrateX supports two kinds of voices:

- **Built-in Kokoro voice IDs** (no extra files; just ensure the `kokoro` package is included)
- **User reference voices** (folders of `.wav` files)

User reference voices are read from the per-user voices directory:

- Windows: `%APPDATA%\NarrateX\voices\<voice_name>\*.wav`

This means you typically *do not* want to bundle `voices/` into the onefile EXE; users can
drop their own reference voices into that folder after install.

## Tests

```powershell
python -m pytest
```

