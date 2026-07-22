"""The voice picker: a gender toggle, a region toggle and a filtered list.

Kokoro voice IDs carry their own taxonomy in the name prefix ("bf_emma" is
British female), so the two toggles filter by prefix and the dropdown only
ever shows the current combination. Region and gender live in data tuples,
so a new region (should Kokoro ever ship one) is one entry here.
"""

from __future__ import annotations

from voice_reader.domain.entities.voice_profile import VoiceProfile

# Display order: British first. Each entry is (prefix, glyph, label).
# Flag glyphs render as boxed GB/US letters on Windows and as flags on
# macOS and Linux; both read correctly.
VOICE_REGIONS = (("b", "🇬🇧", "British"), ("a", "🇺🇸", "American"))
VOICE_GENDERS = (("f", "♀", "Female"), ("m", "♂", "Male"))

# The launch default, chosen deliberately (Kokoro's strongest British
# voice) rather than falling to whatever sorts first alphabetically.
VOICE_DEFAULT_ID = "bf_emma"


def voice_label(voice: VoiceProfile) -> str:
    parts = voice.name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) == 2:
        prefix, raw_name = parts
        region_label = {r[0]: r[2] for r in VOICE_REGIONS}.get(prefix[0])
        gender_label = {g[0]: g[2] for g in VOICE_GENDERS}.get(prefix[1])
        name_label = raw_name.replace("-", " ").replace("_", " ").title()
        if region_label and gender_label:
            return f"{name_label} ({region_label} {gender_label})"
    return voice.name.replace("_", " ").strip().title()


def _matches_filter(name: str, *, region: str, gender: str) -> bool:
    """Prefix-matched voices filter; anything unparseable always shows.

    A voice whose name carries no recognisable prefix would otherwise be
    unreachable through every toggle combination.
    """

    parts = name.split("_", 1)
    if len(parts) != 2 or len(parts[0]) != 2:
        return True
    known_regions = {r[0] for r in VOICE_REGIONS}
    known_genders = {g[0] for g in VOICE_GENDERS}
    if parts[0][0] not in known_regions or parts[0][1] not in known_genders:
        return True
    return parts[0][0] == region and parts[0][1] == gender


def _update_toggle_cues(controller) -> None:
    region = VOICE_REGIONS[controller._voice_region_index]  # noqa: SLF001
    gender = VOICE_GENDERS[controller._voice_gender_index]  # noqa: SLF001

    window = controller.window
    window.btn_voice_region.setText(region[1])
    window.btn_voice_region.setToolTip(f"{region[2]} voices (click to change region)")
    window.btn_voice_gender.setText(gender[1])
    window.btn_voice_gender.setToolTip(f"{gender[2]} voices (click to change)")


def refresh_voices(controller) -> None:
    """Fill the dropdown with the current region and gender combination."""

    region = VOICE_REGIONS[controller._voice_region_index][0]  # noqa: SLF001
    gender = VOICE_GENDERS[controller._voice_gender_index][0]  # noqa: SLF001

    previous = controller.window.voice_combo.currentData()

    voices = [
        v
        for v in controller.voice_service.list_profiles()
        if v.name != "system" and _matches_filter(v.name, region=region, gender=gender)
    ]
    voices.sort(key=lambda v: voice_label(v).casefold())
    controller._voices = voices  # noqa: SLF001

    combo = controller.window.voice_combo
    combo.clear()
    for v in voices:
        combo.addItem(voice_label(v), v.name)
    if not voices:
        combo.addItem("(no voices found)")

    # Keep the user's pick when it survives the filter change; otherwise
    # prefer the deliberate default, else the first entry stands.
    names = [v.name for v in voices]
    if previous in names:
        combo.setCurrentIndex(names.index(previous))
    elif VOICE_DEFAULT_ID in names:
        combo.setCurrentIndex(names.index(VOICE_DEFAULT_ID))

    _update_toggle_cues(controller)


def toggle_voice_gender(controller) -> None:
    controller._voice_gender_index = (  # noqa: SLF001
        controller._voice_gender_index + 1  # noqa: SLF001
    ) % len(VOICE_GENDERS)
    refresh_voices(controller)


def cycle_voice_region(controller) -> None:
    controller._voice_region_index = (  # noqa: SLF001
        controller._voice_region_index + 1  # noqa: SLF001
    ) % len(VOICE_REGIONS)
    refresh_voices(controller)
