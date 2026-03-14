<img width="57" height="48" alt="{CB13D3C4-7566-4A2F-8604-7C4239B293A5}" src="https://github.com/user-attachments/assets/a166e3b6-0c0e-4687-bf4e-f0e55331482c" /> 

# NarrateX (Voice Reader app)

Desktop eBook voice reader built on the Kokoro TTS library: select from multiple machine voices, load a book, and control playback (play/pause/stop) while it reads.

Where available, the UI also displays the book cover and other metadata during book handling.

For a codebase overview (layers, runtime flow, and test mapping), see [`ARCHITECTURE.md`](ARCHITECTURE.md:1).

# Screenshot

<img width="1105" height="726" alt="{07899890-5135-4BC2-A6C8-DD26CE3296A8}" src="https://github.com/user-attachments/assets/bb3f7f7f-4304-4962-8761-faa206ab9851" />

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

## Windows EXE builds

This repository uses **PyInstaller** for Windows EXE builds.

### Notes (Kokoro-only)

The app has been refactored to be **Kokoro-only**:

- No system fallback voice
- No XTTS/Coqui voice cloning

This significantly reduces dependency creep and makes packaging more predictable.

### Build the app EXE (PowerShell)

```powershell
 .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python buildexe.py
```

Output:

- `dist-pyinstaller/NarrateX/NarrateX.exe`

This uses a **onedir** build (recommended). The output folder will also contain
`_internal/` with the PyInstaller runtime and bundled dependencies.

## Windows installer builds

The installer is a separate **onefile** PyInstaller build that embeds a payload
zip of the app bundle.

Build workflow:

1) Build the app bundle (EXE + `_internal/`): [`buildexe.py`](buildexe.py:1)
2) Build the installer (`NarrateXSetup.exe`): [`buildinstaller.py`](buildinstaller.py:1)

### Build installer (PowerShell)

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 1) Build dist-pyinstaller/NarrateX/NarrateX.exe (onedir)
python buildexe.py

# 2) Package payload + build dist-installer/NarrateXSetup.exe (onefile)
python buildinstaller.py
```

Output:

- `dist-installer/NarrateXSetup.exe`

### Troubleshooting

- If the EXE opens then immediately exits, check the crash logs written by [`app.main()`](app.py:55) near the executable.

## Tests

```powershell
python -m pytest
```

