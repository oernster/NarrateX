# Linux Installation

Running NarrateX from source on Linux requires a small number of system libraries before the Python setup.

## System prerequisites

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install libportaudio2 portaudio19-dev python3-venv python3-dev
```

### Fedora / RHEL / CentOS Stream

```bash
sudo dnf install portaudio portaudio-devel python3-devel
```

### Arch Linux / Manjaro

```bash
sudo pacman -S portaudio python
```

### openSUSE

```bash
sudo zypper install portaudio-devel python3-devel
```

`libportaudio2` (or the equivalent package) is required by `sounddevice`, which handles all audio output.
Without it, playback silently hangs: `sounddevice` imports but raises `OSError: PortAudio library not found` at runtime.

## Audio backend

NarrateX works with PulseAudio, PipeWire and ALSA.
No extra configuration is needed for PipeWire (the default on modern Ubuntu, Fedora and Arch installs).
If you are on a headless or minimal system without an audio daemon, install PulseAudio or PipeWire first.

## Python version

The Linux dependency set (`requirements-linux.txt`) is pinned for **Python 3.12** and the wider
Windows set supports 3.10, 3.11 or 3.12. Use 3.12 here; 3.13 and later are not supported by these
pins. (macOS is the exception and is pinned to 3.13 alone, with its own requirements file; see
[DEVELOPMENT-README.md](DEVELOPMENT-README.md).)

Check your version:

```bash
python3 --version
```

If your distro defaults to 3.13+, install 3.12 explicitly:

```bash
# Debian/Ubuntu (deadsnakes PPA)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv python3.12-dev
```

## Install and run

Linux has its own pinned dependency set, `requirements-linux.txt`. Do not use `requirements.txt`
here: that one is pinned for Windows.

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-linux.txt
python app.py
```

## Flatpak

A Flatpak build is available for sandboxed installation without manual dependency management.
Build and install it with [`build_flatpak.sh`](build_flatpak.sh). The script generates the manifest
(`com.oliverernster.narratex.yml`), the launcher, the desktop entry and the metainfo file at build
time, so none of them are tracked; only the script is.

The Flatpak is self-contained: it bundles the PortAudio audio backend, the spaCy
`en_core_web_sm` model and an espeak-ng phonemizer, so none of the system
prerequisites above are needed when running it.

## Native bundle (PyInstaller)

For a non-sandboxed self-contained bundle, build with [`buildlinux.py`](buildlinux.py):

```bash
source venv/bin/activate
python buildlinux.py
```

The output is a onedir bundle in `dist-pyinstaller/NarrateX/` that includes Python,
Qt and all dependencies.

## First-run model download

NarrateX uses the Kokoro-82M TTS model (~300 MB), downloaded automatically from HuggingFace Hub on first run.
The download happens the first time synthesis is attempted (at app startup during warmup).
Expect 15-60 seconds on first launch depending on connection speed.
Subsequent launches load the model from disk cache (`~/.cache/huggingface/hub/`).

## Troubleshooting

**No audio / playback hangs immediately:**
Verify PortAudio is found:

```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
```

If this raises `OSError: PortAudio library not found`, install `libportaudio2` as above and rerun.

**Permission denied on audio device:**
On some systems your user must be in the `audio` group:

```bash
sudo usermod -aG audio $USER
# log out and back in for the change to take effect
```
