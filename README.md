<img width="57" height="48" src="https://github.com/oernster/NarrateX/tree/main/images/narratex-icon.png" /> 

# NarrateX (Voice Reader app)

Desktop eBook voice reader built on the Kokoro TTS library: select from multiple machine voices, load a book, and control playback (play/pause/stop) while it reads.

Where available, the UI also displays the book cover and other metadata during book handling.

For a codebase overview (layers, runtime flow, and test mapping), see [`ARCHITECTURE.md`](ARCHITECTURE.md:1).

# Screenshot

<img width="640" height="480" src="src="https://github.com/oernster/NarrateX/tree/main/images/narratex.png" />  

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

## Tests / Coverage

This repo enforces **100% test coverage** for the configured runtime scope.

- Canonical command: `pytest`
- Coverage config: [`.coveragerc`](.coveragerc:1) and [`pyproject.toml`](pyproject.toml:1)

Fast local iteration without coverage:

- `pytest --no-cov`

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

#### Windows taskbar icon shows the Python icon

If Windows shows the Python icon for the *running* taskbar button (even though the
Explorer/Start Menu icon is correct), it usually means the shell is not grouping
the running process with the packaged EXE identity.

NarrateX enforces a stable identity early in startup by setting:

- Windows AppUserModelID: [`APP_APPUSERMODELID`](voice_reader/version.py:17)
- Qt desktop identity: `QApplication.setDesktopFileName(APP_APPUSERMODELID)` in [`app.main()`](app.py:52)

After rebuilding the EXE once, you may need to refresh the Windows icon cache:

```powershell
ie4uinit.exe -ClearIconCache
taskkill /IM explorer.exe /F
start explorer.exe
```

## Tests

```powershell
python -m pytest
```

