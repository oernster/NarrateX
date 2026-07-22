from __future__ import annotations

from pathlib import Path


def extract_epub_cover(path: Path) -> bytes | None:
    """Extract a representative cover image from an EPUB file (best-effort)."""

    # NOTE:
    # We intentionally use a ZIP-level parser rather than ebooklib metadata
    # helpers. Some real-world EPUBs include cover images that ebooklib doesn't
    # surface as ITEM_IMAGE.
    try:
        import re
        import zipfile

        with zipfile.ZipFile(path) as z:
            names = z.namelist()

            def _read(name: str) -> bytes | None:
                try:
                    return z.read(name)
                except Exception:
                    return None

            def _normalize(path_str: str) -> str:
                parts: list[str] = []
                for part in path_str.replace("\\", "/").split("/"):
                    if part in ("", "."):
                        continue
                    if part == "..":
                        if parts:
                            parts.pop()
                        continue
                    parts.append(part)
                return "/".join(parts)

            def _is_image_target(s: str) -> bool:
                s_l = s.lower().split("?", 1)[0].split("#", 1)[0]
                return s_l.endswith(
                    (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".webp",
                        ".bmp",
                        ".svg",
                    )
                )

            # 1) Find a cover document (cover.xhtml/html).
            cover_docs = [
                n
                for n in names
                if n.lower().endswith(("cover.xhtml", "cover.html", "cover.htm"))
            ]
            if not cover_docs:
                cover_docs = [
                    n
                    for n in names
                    if "cover" in n.lower()
                    and n.lower().endswith((".xhtml", ".html", ".htm"))
                ]

            for doc_name in cover_docs:
                raw = _read(doc_name)
                if not raw:
                    continue
                html = raw.decode("utf-8", errors="ignore")

                matches = re.findall(
                    (
                        r"(?:xlink:href|src|href)\s*=\s*"
                        r"(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))"
                    ),
                    html,
                    flags=re.IGNORECASE,
                )
                if not matches:
                    continue

                # The regex carries three alternative groups, so `findall`
                # yields a tuple per match with exactly one part filled in.
                flat = [part for match in matches for part in match if part]

                href = None
                for cand in flat:
                    if _is_image_target(cand):
                        href = cand
                        break
                # No image-looking link in this cover document. Do not fall back
                # to whatever the first link happens to be: a cover page often
                # links its stylesheet first, and returning that as cover bytes
                # both yields an unreadable image and pre-empts the heuristic
                # scan below that would have found the real cover.
                if href is None:
                    continue
                # An image target never reduces to nothing here: a fragment-only
                # link ("#foo") is not an image target and was already rejected,
                # so stripping a trailing fragment cannot empty the href.
                href = href.split("#", 1)[0]

                base_dir = "/".join(doc_name.split("/")[:-1])
                combined = f"{base_dir}/{href}" if base_dir else href
                candidate = _normalize(combined)

                data = _read(candidate)
                if data:
                    return data

                for n in names:
                    if _normalize(n).endswith(candidate):
                        data2 = _read(n)
                        if data2:
                            return data2

            # 2) Heuristic: choose the first image-like asset.
            image_names = [
                n
                for n in names
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ]
            image_names.sort(key=lambda n: ("cover" not in n.lower(), n.lower()))
            for n in image_names:
                data = _read(n)
                if data:
                    return data
            return None
    except Exception:
        return None
