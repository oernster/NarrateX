# NarrateX - Development & Build Guide

Developer setup, run-from-source, test and packaging instructions for NarrateX.
For the project overview and features, see [README.md](README.md).
For a codebase overview (layers, runtime flow and test mapping), see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Requirements

- Python version and requirements file depend on platform (each platform has its own pinned dependency set):
  - **Windows** (`requirements.txt`): Python 3.10, 3.11 or 3.12 (`kokoro` requires `Python<3.13`)
  - **Linux** (`requirements-linux.txt`): Python 3.12
  - **macOS** (`requirements-mac.txt`): **Python 3.13 only** (3.13.x). This is the sole supported version for the macOS venv - the pinned wheels (e.g. `tokenizers==0.20.3`, built on PyO3 0.22.5) target CPython 3.13 and have no 3.14 wheels, so Python 3.14+ fails to build from source. Earlier 3.x are not supported for this pin set either.
- spaCy `en_core_web_sm` model - installed automatically via the requirements file using the PEP 440 URL format (no separate download step needed)

Optional:

- Calibre (for converting Kindle formats using `ebook-convert`)

**Linux:** system libraries (PortAudio, etc.) must be installed before the Python setup.
See [LINUX-INSTALLATION.md](LINUX-INSTALLATION.md) for distro-specific instructions.

## Install

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Linux

Install the system libraries first (see
[LINUX-INSTALLATION.md](LINUX-INSTALLATION.md) for distro-specific steps), then
create the venv with **Python 3.12** and use `requirements-linux.txt`:

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-linux.txt
```

### macOS

The macOS venv **must** be created with **Python 3.13** (3.13.x). It is the only
supported interpreter for `requirements-mac.txt`: newer versions (3.14+) fail to
build `tokenizers` from source and the pinned wheels target CPython 3.13.

```bash
# Install Python 3.13 if needed:  brew install python@3.13
python3.13 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-mac.txt
```

After installing, apply the `misaki` 0.7.4 patch noted at the top of
`requirements-mac.txt` (fixes a `None` concatenation bug):

```bash
sed -i '' 's/t\.phonemes + t\.whitespace/(t.phonemes or "") + (t.whitespace or "")/g' \
  venv/lib/python3.13/site-packages/misaki/en.py
```

## Run

```powershell
python app.py
```

### Startup behaviour

- Splash screen: enabled by default. Disable with `NARRATEX_DISABLE_SPLASH=1`.
- Single-instance: enabled by default. To allow multiple instances (dev/testing),
  set `NARRATEX_ALLOW_MULTIINSTANCE=1`.
- Window position: the main window is centered on the primary screen automatically at launch.

## Version

`VERSION` at the repository root is the single source of truth and the only place a version string
is written by hand.

- `voice_reader/version.py` reads it at import time (fallback `0.0.0-dev`), so the About dialog, the
  installer header and the Apps-list DisplayVersion all follow it
- `pyproject.toml` declares `version = { file = "VERSION" }`
- every packager ships `VERSION` beside the package, so a frozen build reports the same number as
  the source tree
- the site pages carry delimited tokens refreshed by `stamp_version.py`, which
  [`buildexe.py`](buildexe.py) and [`buildinstaller.py`](buildinstaller.py) call before packaging

To release a new version, edit `VERSION` and nothing else. Run `python stamp_version.py` if you
want the site updated before a build; it is idempotent and prints what it touched.

## Tests / Coverage

This repo enforces **100% test coverage** for the configured runtime scope.

- Canonical command: `pytest`
- Coverage config: [`.coveragerc`](.coveragerc) and [`pyproject.toml`](pyproject.toml)

On Windows, prefer the venv interpreter so a global one cannot be picked up by accident:

```powershell
.venv\Scripts\python.exe -m pytest
```

The gate prints the coverage table last and emits no "N passed" line, so read the exit code rather
than the text: `0` means every test passed and the gate was met.

Fast local iteration without coverage:

- `pytest --no-cov`

## Icons

`narratex.png` at the repository root is the only authored icon. Every other image the build stages
is derived from it by [`generate_icons.py`](generate_icons.py): the eight PNG sizes, the multi-size
Windows `narratex.ico` and the five copies the published site needs under `docs/`. The site needs
its own copies because GitHub Pages publishes `docs/` and nothing above it.

```powershell
python generate_icons.py
python generate_icons.py --check
```

`--check` compares the tracked set against a fresh render and writes nothing, which is the same
comparison [`tests/structural/test_icons_match_master.py`](tests/structural/test_icons_match_master.py)
makes on every test run. Never hand-edit a derived frame: change the master and regenerate.

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

1) Build the app bundle (EXE + `_internal/`): [`buildexe.py`](buildexe.py)
2) Build the installer (`NarrateXSetup.exe`): [`buildinstaller.py`](buildinstaller.py)

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

- If the EXE opens then immediately exits, check the crash logs written by [`app.main()`](app.py) near the executable.

#### Windows taskbar icon shows the Python icon

If Windows shows the Python icon for the *running* taskbar button (even though the
Explorer/Start Menu icon is correct), it usually means the shell is not grouping
the running process with the packaged EXE identity.

NarrateX enforces a stable identity early in startup by setting:

- Windows AppUserModelID: [`APP_APPUSERMODELID`](voice_reader/version.py)
- Qt desktop identity: `QApplication.setDesktopFileName(APP_APPUSERMODELID)` in [`app.main()`](app.py)

After rebuilding the EXE once, you may need to refresh the Windows icon cache:

```powershell
ie4uinit.exe -ClearIconCache
taskkill /IM explorer.exe /F
start explorer.exe
```

## Linux builds

Two build paths are provided for Linux:

- Flatpak (sandboxed, self-contained): build and install with
  [`build_flatpak.sh`](build_flatpak.sh). The Flatpak bundles the audio backend,
  the espeak-ng phonemizer and the spaCy model, so no system dependencies are
  required at run time. It ships its own managed Python runtime with pre-built
  wheels, so the startup Python-window guard detects the sandbox (via
  `/.flatpak-info`) and stands down there. To uninstall and purge the Flatpak,
  use [`cleanup_flatpak.sh`](cleanup_flatpak.sh).
- Native onedir bundle (PyInstaller): build with [`buildlinux.py`](buildlinux.py),
  producing `dist-pyinstaller/NarrateX/`.

Running from source on Linux is covered in
[LINUX-INSTALLATION.md](LINUX-INSTALLATION.md).
