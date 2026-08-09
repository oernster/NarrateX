#!/usr/bin/env python3
"""macOS DMG builder for NarrateX.

Requires macOS with Xcode command-line tools and Homebrew.
Run from the repository root with the venv active:
    python builddmg.py

Notarization is mandatory. A Developer ID signature alone is not enough: since
macOS 10.15 Gatekeeper rejects signed-but-unnotarized apps with "Apple could not
verify ... is free of malware". APPLE_ID and APPLE_APP_PASSWORD must be set or
the build stops before doing any work.

Env vars:
    APPLE_ID                  : Apple ID for notarization (required)
    APPLE_APP_PASSWORD        : app-specific password for notarization (required)
    DEVELOPER_ID_APPLICATION  : override the default signing identity
    APPLE_TEAM_ID             : Team ID for notarization (defaults to W7K465GKFJ)
    ALLOW_UNNOTARIZED         : set to 1 to build without notarizing. The result
                                is for local testing only and must never be
                                published as a release artifact.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import zlib
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

VERSION_FILE = Path(__file__).resolve().parent / "VERSION"
VERSION_FALLBACK = "0.0.0-dev"


def read_version() -> str:
    """Read the repo-root VERSION file, the single source of truth."""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8")
    except OSError:
        return VERSION_FALLBACK
    return text.strip() or VERSION_FALLBACK


# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME = "NarrateX"
APP_VERSION = read_version()
BUNDLE_ID = "uk.codecrafter.NarrateX"
FINAL_DMG = "narratex.dmg"
VOLUME_NAME = f"Install {APP_NAME}"

DEVELOPER_ID = os.environ.get(
    "DEVELOPER_ID_APPLICATION",
    "Developer ID Application: Oliver Ernster (W7K465GKFJ)",
)
APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "W7K465GKFJ")

# The notarization credential for this app, created once with
#   xcrun notarytool store-credentials NarrateX \
#     --apple-id <id> --team-id <team> --password <app-specific>
# One profile per app means a leaked credential can be revoked for a single
# app. Stated explicitly rather than derived from a display name: the profile
# is a fact registered with Apple, and deriving it would silently change which
# credential the build looks for if that name were ever edited.
# APPLE_KEYCHAIN_PROFILE overrides it.
NOTARY_PROFILE = os.environ.get("APPLE_KEYCHAIN_PROFILE", "") or "NarrateX"

# The notary service accepts only an app-specific password from appleid.apple.com
# and rejects the Apple account password with HTTP 401. The shape is distinctive,
# so it is checked before the build rather than discovered after it.
APP_SPECIFIC_PASSWORD_RE = re.compile(r"^[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}$")

# Escape hatch for local test builds. Distribution builds must never set this:
# an unnotarized DMG is rejected by Gatekeeper on every machine but the one that
# signed it, and the failure is invisible at build time.
ALLOW_UNNOTARIZED = os.environ.get("ALLOW_UNNOTARIZED", "") == "1"
# Notarization is the default and the keychain profile always resolves, so the
# only way to skip it is to ask for that explicitly.
NOTARIZING = not ALLOW_UNNOTARIZED

ENTITLEMENTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def require(tool: str, brew_pkg: str | None = None) -> None:
    if shutil.which(tool):
        return
    pkg = brew_pkg or tool
    print(f"{tool} not found, installing via brew...")
    run(["brew", "install", pkg])
    if not shutil.which(tool):
        sys.exit(f"ERROR: {tool} still not found after brew install. Aborting.")


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── Steps ─────────────────────────────────────────────────────────────────────


def check_platform() -> None:
    section("Platform check")
    if sys.platform != "darwin":
        sys.exit("ERROR: This script must run on macOS.")
    result = subprocess.run(
        ["sw_vers", "-productVersion"], capture_output=True, text=True
    )
    print(f"  macOS {result.stdout.strip()}")
    require("pyinstaller", "pyinstaller")
    require("create-dmg", "create-dmg")
    require("codesign")
    print("  All tools present.")


def check_notarization_credentials() -> None:
    """Fail before the build starts if the release cannot be notarized.

    Checked up front rather than at the notarization step so a missing password
    costs seconds instead of a full PyInstaller run.
    """
    section("Notarization credentials")
    if ALLOW_UNNOTARIZED:
        print("  WARNING: ALLOW_UNNOTARIZED=1 set.")
        print("  WARNING: this build is for local testing and must not be released.")
        return
    if APPLE_ID and APPLE_APP_PASSWORD:
        if not APP_SPECIFIC_PASSWORD_RE.match(APPLE_APP_PASSWORD):
            sys.exit(
                "ERROR: APPLE_APP_PASSWORD is not an app-specific password.\n"
                "  Expected four lowercase groups of four, like abcd-efgh-ijkl-mnop.\n"
                "  An Apple account password is rejected by the notary service with\n"
                "  'HTTP status code: 401. Invalid credentials'.\n"
                "  Generate one at https://appleid.apple.com (Sign-In and Security,\n"
                "  App-Specific Passwords), or leave both variables unset and store\n"
                f"  the credential in the keychain as profile {NOTARY_PROFILE}."
            )
        print(f"  Notarizing as {APPLE_ID} (team {APPLE_TEAM_ID}).")
        return
    print(f"  Notarizing with keychain profile {NOTARY_PROFILE}.")


def check_runtime_dependencies() -> None:
    """Fail if anything in requirements.txt is absent from the build interpreter.

    PyInstaller only warns when --collect-submodules names a package it cannot
    find, so a stale venv yields a bundle that builds, signs and notarizes
    cleanly and then dies at launch with ModuleNotFoundError. Checking the
    interpreter that is about to be frozen turns a silent runtime failure into a
    build failure.
    """
    section("Runtime dependencies")
    requirements = Path(__file__).parent / "requirements.txt"
    if not requirements.exists():
        sys.exit(f"ERROR: {requirements.name} not found beside builddmg.py.")

    missing: list[str] = []
    checked = 0
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        # Skip blanks and pip options such as -r or --index-url. Distribution
        # names are what requirements.txt lists, so no import-name mapping is
        # needed: PySide6 and pyobjc-framework-Cocoa both resolve here.
        if not line or line.startswith("-"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as error:
            sys.exit(f"ERROR: cannot parse '{line}' in {requirements.name}: {error}")
        # An environment marker such as sys_platform == "win32" means the package
        # is not wanted on this platform, so its absence is correct rather than a
        # fault. Evaluating the marker beats naming Windows packages here, which
        # would go stale the moment the requirements change.
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        checked += 1
        try:
            metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            missing.append(requirement.name)

    if missing:
        sys.exit(
            "ERROR: the build interpreter is missing "
            f"{len(missing)} of {checked} requirements:\n"
            + "".join(f"    {name}\n" for name in missing)
            + "  PyInstaller would omit them and the app would crash at launch\n"
            "  with ModuleNotFoundError. Install them first:\n"
            f"    pip install -r {requirements.name}"
        )
    print(f"  All {checked} requirements present.")


def notarytool_credentials() -> list[str]:
    """Authentication arguments for notarytool.

    An explicit APPLE_ID and APPLE_APP_PASSWORD pair wins, for CI that has no
    keychain. Otherwise the per-app profile is used, which keeps the secret out
    of the process arguments where any other process could read it via ps.
    """
    if APPLE_ID and APPLE_APP_PASSWORD:
        return [
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
        ]
    return ["--keychain-profile", NOTARY_PROFILE]


def redact(cmd: list[str]) -> str:
    """Render a command with the value after --password masked.

    run() echoes every command it runs, and CalledProcessError repeats the whole
    argument list in its traceback. Both would otherwise copy the app-specific
    password into build logs and CI output.
    """
    parts: list[str] = []
    mask_next = False
    for arg in (str(c) for c in cmd):
        parts.append("********" if mask_next else arg)
        mask_next = arg == "--password"
    return " ".join(parts)


def notarytool_submit(target: Path) -> None:
    """Submit target to Apple and wait for the verdict.

    A failed submission stops the build rather than producing an artifact that
    looks distributable. subprocess is called directly instead of through run()
    so that neither the echoed command nor the failure path exposes the
    password. Stapling is a separate step because the submitted file and the
    file that carries the ticket differ for a .app (a zip is submitted, the
    bundle is stapled).
    """
    cmd = [
        "xcrun",
        "notarytool",
        "submit",
        str(target),
        *notarytool_credentials(),
        "--wait",
    ]
    print(f"  $ {redact(cmd)}")
    if subprocess.run(cmd, check=False).returncode == 0:
        return
    sys.exit(
        "ERROR: notarization failed (notarytool output above).\n"
        "  'No Keychain password item found' means this app has no stored\n"
        "  credential yet. Generate an app-specific password at\n"
        "  https://appleid.apple.com (Sign-In and Security), then:\n"
        f"    xcrun notarytool store-credentials {NOTARY_PROFILE} \\\n"
        "      --apple-id you@example.com --team-id "
        f"{APPLE_TEAM_ID} --password <app-specific>\n"
        "  'HTTP status code: 401' means the credential is wrong: use an\n"
        "  app-specific password, not your Apple account password.\n"
        "  For an 'Invalid' verdict, the per-binary reasons are in:\n"
        "    xcrun notarytool log <submission-id> "
        f"--keychain-profile {NOTARY_PROFILE}"
    )


def clean() -> None:
    section("Clean previous build")
    for path in [
        "build",
        "dist",
        FINAL_DMG,
        "NarrateX.spec",
        "_dmg_staging",
        "_narratex_rw.dmg",
    ]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"  Removed: {path}")


def build_app_bundle(entitlements_path: Path, icns_path: Path | None = None) -> Path:
    section("PyInstaller: build .app bundle")

    root = Path(__file__).parent
    icon_args = ["--icon", str(icns_path)] if icns_path else []

    add_data = [
        # The single source of truth for the version. `voice_reader/version.py`
        # reads it from beside the package, so it has to travel with the bundle
        # or the frozen app reports the 0.0.0-dev fallback.
        f"{root / 'VERSION'}:.",
        f"{root / 'LICENSE'}:.",
        f"{root / 'LGPL3-LICENSE'}:.",
        f"{root / 'narratex.png'}:.",
        f"{root / 'narratex_16.png'}:.",
        f"{root / 'narratex_24.png'}:.",
        f"{root / 'narratex_32.png'}:.",
        f"{root / 'narratex_48.png'}:.",
        f"{root / 'narratex_64.png'}:.",
        f"{root / 'narratex_128.png'}:.",
        f"{root / 'narratex_256.png'}:.",
        f"{root / 'narratex_512.png'}:.",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--osx-bundle-identifier",
        BUNDLE_ID,
        "--codesign-identity",
        DEVELOPER_ID,
        "--osx-entitlements-file",
        str(entitlements_path),
        *icon_args,
        # ── kokoro / TTS stack ─────────────────────────────────────
        "--collect-all=kokoro",
        "--hidden-import=misaki",
        "--collect-data=misaki",
        "--collect-all=phonemizer",
        "--collect-all=espeakng_loader",
        "--collect-all=spacy",
        "--collect-all=en_core_web_sm",
        "--collect-data=language_tags",
        # ── torch ─────────────────────────────────────────────────
        "--collect-binaries=torch",
        "--collect-data=torch",
        "--hidden-import=torch",
        "--hidden-import=torch.distributed.rpc",
        "--exclude-module=tensorboard",
        "--exclude-module=torch.utils.tensorboard",
        "--exclude-module=torch.distributed._sharding_spec",
        "--exclude-module=torch.distributed._sharded_tensor",
        "--exclude-module=torch.distributed._shard.checkpoint",
        # ── transformers / tokenizers ──────────────────────────────
        "--collect-all=transformers",
        # ── scipy (required by kokoro 0.7.x on macOS) ─────────────
        "--collect-all=scipy",
        # ── numpy / audio ──────────────────────────────────────────
        "--collect-all=numpy",
        "--collect-all=soundfile",
        "--hidden-import=soundfile",
        "--collect-binaries=soundfile",
    ]

    # Dynamic wiring (importlib.import_module at runtime): derived from the
    # wiring table so a new entry can never be missing from the frozen build
    # (see the same pattern in buildexe.py).
    from voice_reader.bootstrap import wiring_module_names

    for mod in wiring_module_names():
        cmd.append(f"--hidden-import={mod}")

    for spec in add_data:
        cmd.extend(["--add-data", spec])

    cmd.append(str(root / "app.py"))

    run(cmd)

    app_path = Path("dist") / f"{APP_NAME}.app"
    if not app_path.exists():
        sys.exit(f"ERROR: Expected app bundle not found: {app_path}")
    print(f"  Built: {app_path}")
    return app_path


def strip_build_artifacts(app_path: Path) -> None:
    section("Strip build artifacts")
    # PySide6 ships .cpp.o object files inside its QML plugin directories.
    # They are Mach-O relocatable binaries that codesign --deep silently skips
    # but Gatekeeper flags as unsigned, causing the entire bundle to be rejected.
    removed = 0
    for f in app_path.rglob("*.o"):
        if f.is_file():
            f.unlink()
            removed += 1
    for d in sorted(app_path.rglob("objects-*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"  Removed {removed} intermediate object file(s)")


def sign_bundle(app_path: Path, entitlements_path: Path) -> None:
    section("Code signing")

    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements_path),
            "--sign",
            DEVELOPER_ID,
            str(app_path),
        ]
    )

    run(["codesign", "--verify", "--deep", "--strict", str(app_path)])
    print("  Signature verified.")


def _fill_png_background(path: Path, bg: tuple[int, int, int]) -> None:
    """Composite an RGBA PNG over a solid RGB background colour in-place.

    macOS renders ICNS icons against whatever surface is below them (white in
    Finder/installation windows).  Without an opaque background the transparent
    areas of the icon look white there, while appearing dark in the dark-themed
    app UI.  Filling the background once at ICNS-generation time makes the icon
    consistent everywhere.
    """
    data = path.read_bytes()
    pos, width, height, idat_chunks = 8, 0, 0, []
    while pos < len(data) - 12:
        n = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + n]
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", cdata[0:8])
            if cdata[8] != 8 or cdata[9] != 6:
                return  # not 8-bit RGBA, leave as-is
        elif ctype == b"IDAT":
            idat_chunks.append(cdata)
        pos += 12 + n

    bpp = 4
    filtered = bytearray(zlib.decompress(b"".join(idat_chunks)))
    stride = width * bpp + 1
    pixels = bytearray(height * width * bpp)

    def _paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    for r in range(height):
        filt = filtered[r * stride]
        row = r * width * bpp
        prev_row = (r - 1) * width * bpp
        for i in range(width * bpp):
            x = filtered[r * stride + 1 + i]
            a = pixels[row + i - bpp] if i >= bpp else 0
            b = pixels[prev_row + i] if r > 0 else 0
            c = pixels[prev_row + i - bpp] if r > 0 and i >= bpp else 0
            if filt == 0:
                pixels[row + i] = x
            elif filt == 1:
                pixels[row + i] = (x + a) & 0xFF
            elif filt == 2:
                pixels[row + i] = (x + b) & 0xFF
            elif filt == 3:
                pixels[row + i] = (x + (a + b) // 2) & 0xFF
            elif filt == 4:
                pixels[row + i] = (x + _paeth(a, b, c)) & 0xFF

    br, bg_, bb = bg
    for idx in range(width * height):
        off = idx * 4
        pa = pixels[off + 3]
        if pa == 255:
            continue
        if pa == 0:
            pixels[off], pixels[off + 1], pixels[off + 2], pixels[off + 3] = (
                br,
                bg_,
                bb,
                255,
            )
        else:
            a = pa / 255.0
            pixels[off] = int(pixels[off] * a + br * (1 - a))
            pixels[off + 1] = int(pixels[off + 1] * a + bg_ * (1 - a))
            pixels[off + 2] = int(pixels[off + 2] * a + bb * (1 - a))
            pixels[off + 3] = 255

    raw_out = bytearray()
    for r in range(height):
        raw_out.append(0)
        raw_out.extend(pixels[r * width * bpp : (r + 1) * width * bpp])

    def _chunk(name: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", crc)

    ihdr_payload = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_out = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_payload)
        + _chunk(b"IDAT", zlib.compress(bytes(raw_out), 6))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png_out)


def png_to_icns(png_path: Path, work_dir: Path) -> Path:
    # Dark background matching NarrateX's app theme.
    BG = (0x1A, 0x1A, 0x2A)

    iconset = work_dir / "narratex.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 128, 256, 512]
    for size in sizes:
        for suffix, px in [
            (f"icon_{size}x{size}.png", size),
            (f"icon_{size}x{size}@2x.png", size * 2),
        ]:
            out = iconset / suffix
            run(
                ["sips", "-z", str(px), str(px), str(png_path), "--out", str(out)],
                capture_output=True,
            )
            _fill_png_background(out, BG)
    icns_path = work_dir / "narratex.icns"
    run(["iconutil", "--convert", "icns", str(iconset), "--output", str(icns_path)])
    shutil.rmtree(iconset)
    return icns_path


def _find_mount_point(hdiutil_stdout: str) -> str | None:
    for line in hdiutil_stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[-1].strip().startswith("/Volumes/"):
            return parts[-1].strip()
    return None


def set_volume_icon(icns_path: Path) -> None:
    section("Set volume icon")
    rw_dmg = Path("_narratex_rw.dmg")

    run(["hdiutil", "convert", FINAL_DMG, "-format", "UDRW", "-o", str(rw_dmg)])
    try:
        result = subprocess.run(
            ["hdiutil", "attach", "-noverify", str(rw_dmg)],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  $ hdiutil attach -noverify {rw_dmg}")
        mount_point = _find_mount_point(result.stdout)
        if not mount_point:
            sys.exit(
                f"ERROR: could not find mount point in hdiutil output:\n{result.stdout}"
            )

        try:
            shutil.copy(icns_path, Path(mount_point) / ".VolumeIcon.icns")
            set_file = subprocess.run(
                ["xcrun", "-f", "SetFile"], capture_output=True, text=True
            ).stdout.strip()
            if set_file:
                subprocess.run([set_file, "-a", "C", mount_point], check=True)
            else:
                finder_info = bytearray(32)
                finder_info[8] = 0x04
                subprocess.run(
                    [
                        "xattr",
                        "-wx",
                        "com.apple.FinderInfo",
                        " ".join(f"{b:02x}" for b in finder_info),
                        mount_point,
                    ],
                    check=True,
                )
            print(f"  Volume icon embedded; custom-icon flag set on {mount_point}")
        finally:
            run(["hdiutil", "detach", mount_point], check=False)

        Path(FINAL_DMG).unlink(missing_ok=True)
        run(["hdiutil", "convert", str(rw_dmg), "-format", "UDZO", "-o", FINAL_DMG])
    finally:
        rw_dmg.unlink(missing_ok=True)


def notarize_bundle(app_path: Path) -> None:
    """Notarize and staple the .app before it is placed in the DMG.

    Stapling only the DMG leaves the copied-out .app with no local ticket, so
    Gatekeeper falls back to an online check and the app fails to launch for a
    user who is offline or behind a restrictive network. notarytool only accepts
    archives, so the bundle is zipped with ditto first (ditto preserves the
    symlinks and metadata the embedded signature depends on); the ticket is then
    stapled to the bundle itself, since a zip cannot carry one.
    """
    if not NOTARIZING:
        return
    section("Notarize .app bundle")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{APP_NAME}.zip"
        run(["ditto", "-c", "-k", "--keepParent", str(app_path), str(archive)])
        notarytool_submit(archive)
    run(["xcrun", "stapler", "staple", str(app_path)])
    print("  Bundle notarized and stapled.")


def create_dmg(app_path: Path) -> None:
    section("Create DMG")

    staging = Path("_dmg_staging")
    staging.mkdir(exist_ok=True)
    dest = staging / app_path.name
    if dest.exists():
        shutil.rmtree(dest)
    # symlinks=True is required: macOS frameworks use symlinks (e.g.
    # Python.framework/Python -> Versions/Current/Python). Without it,
    # shutil.copytree dereferences them into regular files, which invalidates
    # all embedded code signatures and causes dlopen failures at runtime.
    run(["ditto", str(app_path), str(dest)])

    if os.path.exists(FINAL_DMG):
        os.remove(FINAL_DMG)

    cmd = [
        "create-dmg",
        "--volname",
        VOLUME_NAME,
        "--window-pos",
        "200",
        "120",
        "--window-size",
        "640",
        "400",
        "--icon-size",
        "100",
        "--text-size",
        "14",
        "--app-drop-link",
        "520",
        "180",
        "--icon",
        f"{APP_NAME}.app",
        "120",
        "180",
        FINAL_DMG,
        str(staging / f"{APP_NAME}.app"),
    ]

    result = run(cmd, check=False)
    if result.returncode not in (0, 2):
        sys.exit(f"ERROR: create-dmg failed (exit {result.returncode})")

    shutil.rmtree(staging)
    print(f"  DMG created: {FINAL_DMG}")


def sign_dmg() -> None:
    section("Sign DMG")
    run(
        [
            "codesign",
            "--force",
            "--sign",
            DEVELOPER_ID,
            FINAL_DMG,
        ]
    )
    print("  DMG signed.")


def notarize_dmg() -> None:
    if not NOTARIZING:
        return
    section("Notarize DMG")
    notarytool_submit(Path(FINAL_DMG))
    run(["xcrun", "stapler", "staple", FINAL_DMG])
    print("  Notarization complete and stapled.")


def verify_dmg() -> None:
    section("Verify DMG")
    run(["codesign", "--verify", FINAL_DMG])
    if not NOTARIZING:
        size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
        print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): UNNOTARIZED, local testing only")
        return
    # stapler validate proves a ticket is attached; spctl replays the check
    # Gatekeeper performs on the end user's machine. Together they catch the
    # silent case where signing succeeded but notarization never happened.
    run(["xcrun", "stapler", "validate", FINAL_DMG])
    run(["spctl", "--assess", "--type", "install", "-vv", FINAL_DMG])
    size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
    print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): notarized, ready for distribution")


def apply_file_icon(png_path: Path) -> None:
    section("Apply file icon")
    require("fileicon")
    run(["fileicon", "set", FINAL_DMG, str(png_path)])
    print(f"  Icon applied to {FINAL_DMG}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    print(f"\nNARRATEX DMG BUILDER  v{APP_VERSION}")
    print(f"Signing identity: {DEVELOPER_ID}")

    check_platform()
    check_runtime_dependencies()
    check_notarization_credentials()
    clean()

    with tempfile.NamedTemporaryFile(
        suffix=".entitlements", mode="w", delete=False
    ) as f:
        f.write(ENTITLEMENTS)
        entitlements_path = Path(f.name)

    with tempfile.TemporaryDirectory() as icon_tmp:
        png_path = Path(__file__).parent / "narratex.png"
        icns_path = png_to_icns(png_path, Path(icon_tmp)) if png_path.exists() else None
        if not icns_path:
            print(f"  WARNING: {png_path} not found, building without custom icon.")

        try:
            app_path = build_app_bundle(entitlements_path, icns_path)
            strip_build_artifacts(app_path)
            sign_bundle(app_path, entitlements_path)
            notarize_bundle(app_path)
            create_dmg(app_path)
            # Both icon steps rewrite the DMG, so they run before it is signed
            # and notarized. Doing either afterwards would modify a file that
            # Gatekeeper has already been told the hash of.
            if icns_path:
                set_volume_icon(icns_path)
                apply_file_icon(png_path)
            sign_dmg()
            notarize_dmg()
            verify_dmg()
        finally:
            entitlements_path.unlink(missing_ok=True)

    print(f"\nDone.  Distribute: {FINAL_DMG}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
