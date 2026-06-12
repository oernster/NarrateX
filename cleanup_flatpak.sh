#!/usr/bin/env bash
# cleanup_flatpak.sh - Uninstall and purge NarrateX Flatpak
set -euo pipefail

APP_ID="com.oliverernster.narratex"

bold=$(tput bold 2>/dev/null || true)
reset=$(tput sgr0 2>/dev/null || true)
section() { echo; echo "${bold}=== $* ===${reset}"; }

section "Uninstalling ${APP_ID}"
if flatpak list --user | grep -q "${APP_ID}"; then
    flatpak uninstall --user -y "${APP_ID}"
    echo "  Uninstalled."
else
    echo "  Not installed, skipping."
fi

section "Removing build artefacts"
rm -f narratex.flatpak
rm -rf .flatpak-build .flatpak-repo .flatpak-builder .flatpak-wheels
rm -rf dist-pyinstaller build
rm -f "${APP_ID}.yml"
rm -rf packaging/
echo "  Done."

echo
echo "${bold}Purge complete.${reset}"
