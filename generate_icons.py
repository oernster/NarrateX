"""Emit every icon asset in the repository from the one master image.

Run from the repository root:

    python generate_icons.py

`narratex.png` is the master and the only icon file that is authored. Everything
else here is derived from it, so the set cannot drift from its own source:

    narratex_<size>.png   the sizes the delivery scripts stage (buildexe,
                          buildinstaller, buildlinux, builddmg) and the Flatpak
                          hicolor tree installs
    narratex.ico          the Windows PE icon and shortcut icon
    docs/narratex_<size>.png
                          the site's favicons and touch icons. GitHub Pages
                          publishes docs/ and nothing above it, so the site
                          cannot reference the copies at the root and needs its
                          own. Generated rather than copied by hand, which is
                          the whole point of this script.

The master is 487x487, so `narratex_512.png` is a slight upscale. That is how
the existing set was produced and this script reproduces it exactly; a larger
master would be an improvement to make deliberately rather than by accident.

The script is idempotent: run it twice and the second run reports nothing
written. Pass --check to compare without writing, which is what a verification
step wants.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
MASTER = PROJECT_ROOT / "narratex.png"

# Every size any consumer stages. The Flatpak hicolor tree installs all eight.
PNG_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256, 512)

# The Windows icon carries every size but 512: Explorer never asks for one that
# large and it would double the file for nothing.
ICO_PATH = PROJECT_ROOT / "narratex.ico"
ICO_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)

# The published site, which cannot reach the copies above it.
SITE_DIR = PROJECT_ROOT / "docs"
SITE_SIZES: tuple[int, ...] = (16, 32, 64, 256, 512)

RESAMPLE = Image.Resampling.LANCZOS


def png_name(size: int) -> str:
    return f"narratex_{size}.png"


def load_master() -> Image.Image:
    if not MASTER.is_file():
        raise SystemExit(f"Master icon not found: {MASTER}")
    master = Image.open(MASTER).convert("RGBA")
    if master.width != master.height:
        raise SystemExit(f"Master icon must be square, got {master.size}")
    return master


def render(master: Image.Image, size: int) -> Image.Image:
    return master.resize((size, size), RESAMPLE)


def png_bytes(image: Image.Image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ico_bytes(master: Image.Image) -> bytes:
    """Every frame rendered from the master, never resampled from each other.

    Given only a base image and a size list, the ICO writer derives the smaller
    frames from the base with its own resampling, so a 24px frame ends up a
    resize of a resize. Passing each frame explicitly means every one is a
    direct LANCZOS reduction of the master, which is what the small sizes need
    to stay legible.
    """

    from io import BytesIO

    frames = [render(master, size) for size in sorted(ICO_SIZES)]
    buffer = BytesIO()
    frames[-1].save(
        buffer,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[:-1],
    )
    return buffer.getvalue()


def targets(master: Image.Image) -> dict[Path, bytes]:
    """Every file this script owns, mapped to the bytes it should hold."""

    wanted: dict[Path, bytes] = {}
    for size in PNG_SIZES:
        wanted[PROJECT_ROOT / png_name(size)] = png_bytes(render(master, size))
    for size in SITE_SIZES:
        wanted[SITE_DIR / png_name(size)] = png_bytes(render(master, size))
    wanted[ICO_PATH] = ico_bytes(master)
    return wanted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change without writing anything",
    )
    args = parser.parse_args(argv)

    master = load_master()
    print(f"master: {MASTER.name} {master.size[0]}x{master.size[1]}")

    stale: list[Path] = []
    for path, data in targets(master).items():
        current = path.read_bytes() if path.is_file() else None
        if current == data:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    if not stale:
        print("every icon already matches the master; nothing to do.")
        return 0

    verb = "would rewrite" if args.check else "wrote"
    print(f"{verb}:")
    for path in stale:
        print(f"  {path.relative_to(PROJECT_ROOT).as_posix()}")
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
