#!/usr/bin/env bash
# build_flatpak.sh - Build NarrateX as a Flatpak
#
# Uses org.freedesktop.Platform//25.08 (Python 3.13, glibc 2.42).
# All Python packages are pre-downloaded on the host for speed, then
# installed inside the flatpak sandbox from local wheels.
#
# Usage:
#   ./build_flatpak.sh            - build, install locally, and write
#                                   narratex.flatpak to the repo base dir
#   ./build_flatpak.sh --bundle   - accepted for backwards compatibility;
#                                   the bundle is now always produced

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/venv/bin/activate"

APP_ID="com.oliverernster.narratex"
APP_VERSION=$(python3 -c "exec(open('voice_reader/version.py').read()); print(__version__)")
# Absolute so the bundle always lands in the repo base dir, whatever the cwd.
BUNDLE="${SCRIPT_DIR}/narratex.flatpak"
BUILD_DIR=".flatpak-build"
REPO_DIR=".flatpak-repo"
MANIFEST="${APP_ID}.yml"

RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="25.08"

# spaCy English model required by misaki (kokoro's grapheme-to-phoneme stage).
# Not on PyPI: published as a GitHub release wheel, versioned to spaCy's
# major.minor.  Must stay in sync with the spacy pin in requirements-flatpak.txt.
# Without it, misaki calls spacy.cli.download() at first synthesis, which shells
# out to uv pip install, fails in the read-only sandbox, and sys.exit(2) silently
# kills the narration thread (no audio, no visible error).
SPACY_MODEL="en_core_web_sm"
SPACY_MODEL_VERSION="3.8.0"
SPACY_MODEL_WHEEL="${SPACY_MODEL}-${SPACY_MODEL_VERSION}-py3-none-any.whl"
SPACY_MODEL_WHEEL_URL="https://github.com/explosion/spacy-models/releases/download/${SPACY_MODEL}-${SPACY_MODEL_VERSION}/${SPACY_MODEL_WHEEL}"

# A distributable single-file bundle is always written to the repo base dir.
# The historical --bundle flag is accepted but no longer required.
MAKE_BUNDLE=1

# ── Colour helpers ────────────────────────────────────────────────────────────
bold=$(tput bold 2>/dev/null || true)
reset=$(tput sgr0 2>/dev/null || true)
section() { echo; echo "${bold}=== $* ===${reset}"; }

run_with_spinner() {
    local label="$1" watch=""
    shift
    if [[ "${1:-}" == "--watch" ]]; then watch="$2"; shift 2; fi
    [[ "${1:-}" == "--" ]] && shift
    "$@" &
    local pid=$! i=0 spin='⣾⣽⣻⢿⡿⣟⣯⣷'
    while kill -0 "$pid" 2>/dev/null; do
        local extra=""
        if [[ -n "$watch" && -f "$watch" ]]; then
            extra="  ($(du -sh "$watch" 2>/dev/null | cut -f1) written)"
        fi
        printf "\r  %s  %s%s" "${spin:$((i % ${#spin})):1}" "$label" "$extra"
        i=$((i + 1)); sleep 0.3
    done
    wait "$pid"; local rc=$?
    [[ $rc -eq 0 ]] && printf "\r  ✓  %-72s\n" "$label" \
                     || printf "\r  ✗  %-72s\n" "$label"
    return $rc
}

# ── Tool checks ───────────────────────────────────────────────────────────────
section "Checking dependencies"
install_if_missing() {
    local pkg="$1"
    if ! command -v "$pkg" &>/dev/null; then
        echo "  $pkg not found - installing..."
        if   command -v apt-get &>/dev/null; then sudo apt-get update -qq && sudo apt-get install -y "$pkg"
        elif command -v dnf    &>/dev/null; then sudo dnf install -y "$pkg"
        elif command -v pacman &>/dev/null; then sudo pacman -Sy --noconfirm "$pkg"
        else echo "ERROR: unsupported package manager" >&2; exit 1; fi
    else echo "  $pkg: OK"; fi
}
install_if_missing flatpak
install_if_missing flatpak-builder

# ── Flatpak remote + runtime ──────────────────────────────────────────────────
section "Configuring Flathub remote"
flatpak remote-add --if-not-exists --user flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo

section "Installing runtime and SDK (25.08)"
flatpak install --user --noninteractive flathub \
    "${RUNTIME}//${RUNTIME_VERSION}" \
    "${SDK}//${RUNTIME_VERSION}" \
    org.freedesktop.Sdk.Extension.rust-stable//${RUNTIME_VERSION} \
    || true

# ── Pre-download wheels (Python 3.13 / manylinux x86_64) ─────────────────────
# Downloading on the host avoids slow sandboxed network calls.
# Target matches the SDK: Python 3.13, manylinux_2_28_x86_64 (glibc 2.17+).
section "Pre-downloading wheels (Python 3.13 / manylinux x86_64)"
mkdir -p .flatpak-wheels

_dl() {
    local req="$1"
    # Pass 1a: manylinux2014 tag - covers the majority of packages whose cp313
    #          wheels are tagged manylinux2014_x86_64 / manylinux_2_17_x86_64.
    pip download --no-deps --only-binary :all: \
        --python-version 3.13 --implementation cp \
        --platform manylinux2014_x86_64 \
        -q -d .flatpak-wheels "$req" 2>/dev/null && return 0
    # Pass 1b: manylinux_2_28 tag - covers packages whose cp313 wheels use
    #          the newer manylinux_2_27 / manylinux_2_28 tags (e.g. contourpy).
    pip download --no-deps --only-binary :all: \
        --python-version 3.13 --implementation cp \
        --platform manylinux_2_28_x86_64 \
        -q -d .flatpak-wheels "$req" 2>/dev/null && return 0
    # Pass 2: pure-Python sdist / universal wheel fallback.
    pip download --no-deps --prefer-binary \
        -q -d .flatpak-wheels "$req" 2>/dev/null && return 0
    echo "  WARNING: could not download: $req"
}

total=$(grep -cE '^[^#[:space:]]' requirements-flatpak.txt || true)
echo "  Downloading ${total} packages..."
while IFS= read -r req || [[ -n "$req" ]]; do
    [[ -z "${req// }" || "$req" == \#* ]] && continue
    _dl "$req"
done < requirements-flatpak.txt

_dl "uv"

echo "  Downloading torch CPU-only..."
pip download --no-deps --only-binary :all: \
    --python-version 3.13 --implementation cp \
    --platform linux_x86_64 \
    --index-url https://download.pytorch.org/whl/cpu \
    -q -d .flatpak-wheels torch

# Pure-Python (py3-none-any) model wheel; downloads regardless of target platform.
echo "  Downloading ${SPACY_MODEL} spaCy model (misaki G2P dependency)..."
pip download --no-deps -q -d .flatpak-wheels "${SPACY_MODEL_WHEEL_URL}"

echo "  $(ls .flatpak-wheels/ | wc -l) distributions ready"

# ── Packaging helpers ─────────────────────────────────────────────────────────
section "Writing packaging helpers"
mkdir -p packaging

cp narratex_512.png packaging/narratex-icon.png

# Python 3.13 site-packages path (matches the SDK's Python version)
cat > packaging/narratex-launcher.sh <<'LAUNCHER'
#!/bin/sh
# Tell Config to use platformdirs (~/.local/share/NarrateX) instead of
# trying to write beside app.py, which is read-only inside the flatpak.
export NARRATEX_USER_DIRS=1
export LD_LIBRARY_PATH="/app/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="/app/share/narratex:/app/lib/python3.13/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export QT_PLUGIN_PATH="/app/lib/python3.13/site-packages/PySide6/Qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="/app/lib/python3.13/site-packages/PySide6/Qt/plugins/platforms"
export QML2_IMPORT_PATH="/app/lib/python3.13/site-packages/PySide6/Qt/qml"
export QTWEBENGINE_DISABLE_SANDBOX=1
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${FORCE_X11:-}" ]; then
    export QT_QPA_PLATFORM=wayland
elif [ -n "${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
else
    export QT_QPA_PLATFORM=xcb
fi
exec python3 /app/share/narratex/app.py "$@"
LAUNCHER
chmod +x packaging/narratex-launcher.sh

cat > "packaging/${APP_ID}.desktop" <<DESKTOP
[Desktop Entry]
Name=NarrateX
Comment=Desktop reading system that converts structured books into continuous audio playback
Exec=narratex
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
DESKTOP

cat > "packaging/${APP_ID}.metainfo.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>NarrateX</name>
  <summary>EPUB and PDF book narration with Kokoro TTS</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>LGPL-3.0</project_license>
  <description>
    <p>NarrateX is a desktop reading system that converts structured EPUB and PDF books
    into continuous audio playback using the Kokoro text-to-speech engine.</p>
  </description>
  <releases>
    <release version="${APP_VERSION}" date="$(date +%Y-%m-%d)"/>
  </releases>
  <url type="homepage">https://www.narratex.co.uk</url>
</component>
XML

echo "  Packaging helpers ready."

# ── Manifest ──────────────────────────────────────────────────────────────────
section "Writing manifest ${MANIFEST}"

cat > "${MANIFEST}" <<YAML
app-id: ${APP_ID}
runtime: ${RUNTIME}
runtime-version: "${RUNTIME_VERSION}"
sdk: ${SDK}

# Rust is needed to build curated-tokenizers, which has no cp313 wheel.
sdk-extensions:
  - org.freedesktop.Sdk.Extension.rust-stable

command: narratex

build-options:
  build-args:
    - --share=network
  # Make cargo available to all modules.
  append-path: /usr/lib/sdk/rust-stable/bin
  strip: true
  no-debuginfo: true
  env:
    CCACHE_DISABLE: "1"

finish-args:
  - --share=network
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --socket=pulseaudio
  - --device=dri
  - --filesystem=home
  - --env=QTWEBENGINE_DISABLE_SANDBOX=1

modules:

  # ── pip + uv from pre-downloaded local wheels ─────────────────────────────
  - name: python3-pip
    buildsystem: simple
    build-commands:
      - python3 -m ensurepip --upgrade --default-pip
      - pip3 install --no-cache-dir --no-index --find-links wheels --prefix=/app uv
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels

  # ── PortAudio (C library required by the sounddevice Python wheel) ─────────
  # sounddevice uses ctypes to load libportaudio.so.2 at runtime.
  # PortAudio 19.7.0 cmake has no PulseAudio backend on Linux (only ALSA/JACK).
  # We build with ALSA only; the freedesktop runtime ships libasound with
  # 99-pulseaudio-default.conf which sets pcm.!default to type pulse, so ALSA
  # output flows through libpulse -> the PulseAudio socket (--socket=pulseaudio).
  - name: portaudio
    buildsystem: cmake-ninja
    config-opts:
      - -DCMAKE_BUILD_TYPE=Release
      - -DCMAKE_POLICY_VERSION_MINIMUM=3.5
      - -DPA_BUILD_SHARED=ON
      - -DPA_BUILD_STATIC=OFF
      - -DPA_USE_ALSA=ON
      - -DPA_USE_JACK=OFF
      - -DPA_USE_OSS=OFF
    sources:
      - type: git
        url: https://github.com/PortAudio/portaudio.git
        tag: v19.7.0

  # ── PyTorch CPU-only - forced local to prevent CUDA version being pulled ───
  - name: torch-cpu
    buildsystem: simple
    build-commands:
      - /app/bin/uv pip install --no-cache --no-index --no-deps --find-links wheels --prefix /app torch
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels

  # ── curated-tokenizers / curated-transformers ─────────────────────────────
  # No cp313 wheel on PyPI for any version - built from source via Rust.
  # Isolated here so --no-index on python-deps still blocks CUDA downloads.
  - name: curated-tokenizers
    buildsystem: simple
    build-options:
      env:
        CARGO_HOME: /run/build/curated-tokenizers/.cargo
    build-commands:
      - /app/bin/uv pip install --no-cache --find-links wheels --prefix /app
          curated-tokenizers==0.0.9 curated-transformers==0.1.1
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels

  # ── Python dependencies (local wheels only - --no-index blocks CUDA) ──────
  - name: python-deps
    buildsystem: simple
    build-commands:
      # Override numpy: kokoro pins numpy==1.26.4 but numpy 2.x has cp313 wheels
      # and is runtime-compatible. Without the override, uv would try to build
      # numpy 1.26.4 from source which fails in the flatpak sandbox.
      # --no-index forces uv to use only pre-downloaded wheels and never query
      # PyPI.  Without it, uv fetches torch's dep metadata from PyPI (which
      # declares nvidia/CUDA packages) even though we installed the CPU-only
      # wheel.  The CPU wheel's own metadata has no CUDA deps at all.
      - printf 'numpy>=2.0\nsympy>=1.13.1\n' > version-overrides.txt
      # ${SPACY_MODEL} is installed explicitly (by name, resolved from the local
      # wheel) so misaki never triggers a runtime spacy.cli.download().
      - /app/bin/uv pip install --no-cache --no-index --find-links wheels --prefix /app
          --override version-overrides.txt
          -r requirements-flatpak.txt
          ${SPACY_MODEL}==${SPACY_MODEL_VERSION}
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels
      - type: file
        path: requirements-flatpak.txt

  # ── NarrateX application source ───────────────────────────────────────────
  - name: narratex
    buildsystem: simple
    build-commands:
      - mkdir -p /app/share/narratex
      - cp -r app.py voice_reader voices /app/share/narratex/
      - cp LICENSE LGPL3-LICENSE /app/share/narratex/
      - install -m644 narratex_16.png narratex_24.png narratex_32.png
          narratex_48.png narratex_64.png narratex_128.png
          narratex_256.png narratex_512.png /app/share/narratex/
      - install -Dm644 narratex_16.png  /app/share/icons/hicolor/16x16/apps/${APP_ID}.png
      - install -Dm644 narratex_24.png  /app/share/icons/hicolor/24x24/apps/${APP_ID}.png
      - install -Dm644 narratex_32.png  /app/share/icons/hicolor/32x32/apps/${APP_ID}.png
      - install -Dm644 narratex_48.png  /app/share/icons/hicolor/48x48/apps/${APP_ID}.png
      - install -Dm644 narratex_64.png  /app/share/icons/hicolor/64x64/apps/${APP_ID}.png
      - install -Dm644 narratex_128.png /app/share/icons/hicolor/128x128/apps/${APP_ID}.png
      - install -Dm644 narratex_256.png /app/share/icons/hicolor/256x256/apps/${APP_ID}.png
      - install -Dm644 narratex_512.png /app/share/icons/hicolor/512x512/apps/${APP_ID}.png
      - install -Dm755 packaging/narratex-launcher.sh /app/bin/narratex
      - install -Dm644 packaging/${APP_ID}.desktop /app/share/applications/${APP_ID}.desktop
      - install -Dm644 packaging/${APP_ID}.metainfo.xml /app/share/metainfo/${APP_ID}.metainfo.xml
      - install -Dm644 LICENSE /app/share/licenses/${APP_ID}/LICENSE
      - install -Dm644 LGPL3-LICENSE /app/share/licenses/${APP_ID}/LGPL3-LICENSE
    sources:
      - type: dir
        path: .
YAML

echo "  Manifest written."

# ── Build ─────────────────────────────────────────────────────────────────────
section "Building Flatpak"
rm -rf "${BUILD_DIR}" "${REPO_DIR}"

flatpak-builder \
    --user \
    --install-deps-from=flathub \
    --install \
    --force-clean \
    --repo="${REPO_DIR}" \
    "${BUILD_DIR}" \
    "${MANIFEST}"

# ── Bundle (opt-in) ───────────────────────────────────────────────────────────
if [[ $MAKE_BUNDLE -eq 1 ]]; then
    section "Bundling to ${BUNDLE}"
    echo "  The spinner shows how much of ${BUNDLE} has been written."
    echo
    rm -f "${BUNDLE}"
    run_with_spinner "Writing ${BUNDLE}" --watch "${BUNDLE}" -- \
        flatpak build-bundle "${REPO_DIR}" "${BUNDLE}" "${APP_ID}"
    echo
    echo "${bold}Bundle: ${BUNDLE}  ($(du -sh "${BUNDLE}" | cut -f1))${reset}"
    echo
    echo "Install on another machine:"
    echo "  1. Copy ${BUNDLE} to the target machine"
    echo "  2. flatpak install --user ${BUNDLE}"
    echo "  3. flatpak run ${APP_ID}"
fi

echo
echo "${bold}Build complete.${reset}"
echo
echo "The app is already installed locally.  To manage it:"
echo
echo "  Run:        flatpak run ${APP_ID}"
echo "  Uninstall:  flatpak uninstall --user ${APP_ID}"
echo
echo "Distributable bundle written to:  ${BUNDLE}"
echo
