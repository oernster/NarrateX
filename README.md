<img width="57" height="48" src="images/narratex-icon.png" /> [NarrateX](https://www.narratex.co.uk)

# NarrateX (Voice Reader app)

NarrateX is a desktop reading system that converts structured books into continuous audio playback.
It reads EPUB, PDF, plain text and Markdown, preserves document structure and provides deterministic
navigation through sections and chapters. It handles real-world book formats, including
Kindle-compatible content and multi-book compilations.

NarrateX treats books as structured systems rather than raw text. Everything runs on your machine:
the neural voice, the parsing and the audio cache. Nothing you read leaves the device.

## Who it is for

- Readers with a large ebook library and little time to sit and read it
- Anyone who wants to listen to a book while doing something else, on a wired or wireless headset
- People who need a document read aloud predictably, with the frontmatter, page numbers and
  back-of-book index left out
- Developers who want a worked clean-architecture PySide6 application with the boundaries enforced
  by tests rather than by convention

## Who it is not for

- Mobile users. NarrateX is a desktop application: Windows, macOS and Linux. There is no phone or
  tablet build and none is planned.
- Anyone wanting cloud voices, an account or a subscription. There are none and there is no
  network call in the reading path.
- Anyone wanting voice cloning or a custom voice. NarrateX is Kokoro-only and ships Kokoro's
  English inventory as it stands.
- DRM-locked books. NarrateX reads files you can already open; it does not strip protection.
- Non-English narration. The shipped voice inventory is English (British and American) only.

## Capabilities

- Playback follows document structure rather than file order
- Section navigation is derived from headings and bookmarks
- Non-content is excluded from narration by structure rather than by guesswork: page numbers,
  running heads, contents entries and the back-of-book index are shown where they belong and never
  read aloud; PDF running heads and margin folios are stripped from the extracted text itself so
  they can never be indexed, narrated or displayed
- Navigation loads immediately and processes in the background
- Opening a book never freezes the window: parsing, structure and cover extraction run in a
  separate process while the interface stays responsive, with a live loading indicator
- Voice choice is explicit: a sex toggle and a region toggle (British or American, Kokoro's full
  28-voice English inventory) filter the dropdown, no voice is pre-selected and an amber prompt
  asks for a choice once a book loads
- One consistent control language: a green ring on hover and keyboard focus, a red ring on any
  disabled control, everywhere including dialogs
- Full keyboard reachability as one explicit focus ring: Tab and Right step forward, Shift+Tab and
  Left step back, the ring wraps and follows the visual order, Enter activates like Space,
  dropdowns open on Down and commit on Space or Tab and nothing is focused on launch
- Remove current book (the ❌ beside Select Book) forgets bookmarks, resume position, ideas map,
  cached audio and the auto-load preference after a confirmation; the book file on disk is never
  touched
- Progress names the chapter being read and Previous and Next step by chapters
- Playback position is deterministic and consistent across sessions
- Separator-only divider lines in source texts (e.g. `---`) are treated as non-content and ignored
  during playback
- Click-to-seek: clicking in the reader restarts narration from the nearest chunk boundary
  (chunk-relative seeking)

## Supported book formats

Native:

- EPUB (`.epub`)
- PDF (`.pdf`)
- Plain text (`.txt`)
- Markdown (`.md`, `.markdown`)

Kindle formats (via optional Calibre conversion to EPUB):

- MOBI (`.mobi`)
- AZW (`.azw`)
- AZW3 (`.azw3`)
- PRC (`.prc`)
- KFX (`.kfx`)

## Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.10 to 3.12 (the macOS dependency set pins 3.13) |
| User interface | PySide6 widgets, with a controller bridging UI events to application services |
| Speech synthesis | Kokoro, running on-device, with an espeak-ng phonemizer for out-of-dictionary words |
| Audio output | `sounddevice` over PortAudio, with an `afplay` path on macOS |
| Book parsing | ebooklib (EPUB), PyMuPDF (PDF) and an in-house pure-domain document model |
| Kindle conversion | Calibre `ebook-convert`, optional |
| Persistence | JSON bookmark, preference and ideas stores plus a filesystem audio cache |
| Tests | pytest with a 100% coverage gate over the configured runtime scope |
| Format and lint | black (88), flake8, ruff |
| Packaging | PyInstaller (Windows onedir plus installer, Linux onedir, macOS DMG) and Flatpak |
| Licence | GPL-3.0, with the reusable UI layer under LGPL-3.0 |

## Architecture

<p align="center">
  <img src="docs/site-images/architecture.svg" alt="NarrateX clean architecture: UI, Application, Domain, Infrastructure, with dependencies pointing inward to a pure Domain" width="860">
</p>

NarrateX uses a clean, four-layer architecture with every dependency pointing inward to a pure
Domain that has no I/O and no framework. Layer boundaries, the composition-root whitelist and the
400-line module limit are enforced by AST structural tests at every test run. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the invariants and the full design;
[ARCHITECTURE_CONSTRAINTS.md](ARCHITECTURE_CONSTRAINTS.md) holds the constraints themselves.

# Screenshot

<img width="1050" height="606" src="images/narratex.png" />

## Install and run

Full developer setup, including the per-platform dependency sets, is in
[DEVELOPMENT-README.md](DEVELOPMENT-README.md). The short version on Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Linux needs its system audio libraries first; see [LINUX-INSTALLATION.md](LINUX-INSTALLATION.md).
macOS uses `requirements-mac.txt` and a Python 3.13 virtual environment.

On first run NarrateX downloads the Kokoro model weights (around 300 MB) from HuggingFace Hub.
Every run after that is offline.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The suite runs under a strict 100% coverage gate, so the coverage table prints last and there is no
"N passed" line. Read the exit code: `0` means every test passed and the gate was met. Testing
conventions and the structural suite are documented in [TESTING.md](TESTING.md).

## Build

```powershell
python buildexe.py
python buildinstaller.py
```

That produces `dist-pyinstaller/NarrateX/NarrateX.exe` and then
`dist-installer/NarrateXSetup.exe`. Linux builds with `build_flatpak.sh` (Flatpak) or
`buildlinux.py` (onedir bundle); macOS builds with `builddmg.py`. Every packager reads the version
from the repo-root `VERSION` file and stamps the site pages from it, so no build can ship a
mismatched number.

## Licence

NarrateX is free software. The application is released under the GNU General Public License v3.0
([LICENSE](LICENSE)) and the reusable Qt user-interface layer under the GNU Lesser General Public
License v3.0 ([LGPL3-LICENSE](LGPL3-LICENSE)), aligning with Qt's own licensing.

For the standing reference to what is still open, what is deliberately left and what only looks
like debt, see [TECH_DEBT.md](TECH_DEBT.md).
