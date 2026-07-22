"""The voice picker: a sex toggle, a region toggle and a filtered list.

Kokoro voice IDs carry their own taxonomy in the name prefix ("bf_emma" is
British female), so the two toggles filter by prefix and the dropdown only
ever shows the current combination. Region and sex live in data tuples,
so a new region (should Kokoro ever ship one) is one entry here.

No voice is defaulted. Before a book loads the picker is disabled behind
its placeholder; when a book lands the picker gains an amber attention
ring that flashes until the user first touches it, stays steady until a
voice is chosen and then clears. Pre-synthesis starts at selection time.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer

from voice_reader.domain.entities.voice_profile import VoiceProfile

# Display order: British first. Each entry is (prefix, glyph, label).
# Flag glyphs render as boxed GB/US letters on Windows and as flags on
# macOS and Linux; both read correctly.
VOICE_REGIONS = (("b", "🇬🇧", "British"), ("a", "🇺🇸", "American"))
VOICE_SEXES = (("f", "♀", "Female"), ("m", "♂", "Male"))

# The attention ring's half period: one second on, one second off, so the
# full flash cycle is two seconds.
ATTENTION_FLASH_HALF_PERIOD_MS = 1000


def voice_label(voice: VoiceProfile) -> str:
    parts = voice.name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) == 2:
        prefix, raw_name = parts
        region_label = {r[0]: r[2] for r in VOICE_REGIONS}.get(prefix[0])
        sex_label = {g[0]: g[2] for g in VOICE_SEXES}.get(prefix[1])
        name_label = raw_name.replace("-", " ").replace("_", " ").title()
        if region_label and sex_label:
            return f"{name_label} ({region_label} {sex_label})"
    return voice.name.replace("_", " ").strip().title()


def _matches_filter(name: str, *, region: str, sex: str) -> bool:
    """Prefix-matched voices filter; anything unparseable always shows.

    A voice whose name carries no recognisable prefix would otherwise be
    unreachable through every toggle combination.
    """

    parts = name.split("_", 1)
    if len(parts) != 2 or len(parts[0]) != 2:
        return True
    known_regions = {r[0] for r in VOICE_REGIONS}
    known_sexes = {g[0] for g in VOICE_SEXES}
    if parts[0][0] not in known_regions or parts[0][1] not in known_sexes:
        return True
    return parts[0][0] == region and parts[0][1] == sex


def book_is_loaded(controller) -> bool:
    """Whether the service can prove a loaded book.

    Permissive on purpose: a service (or test fake) without the probe is
    treated as loaded, exactly like the transport's own guard.
    """

    probe = getattr(controller.narration_service, "loaded_book", None)
    if not callable(probe):
        return True
    try:
        return probe() is not None
    except Exception:
        return True


def _update_toggle_cues(controller) -> None:
    from PySide6.QtGui import QIcon

    from voice_reader.ui._main_window_controls import emoji_cue_pixmap

    region = VOICE_REGIONS[controller._voice_region_index]  # noqa: SLF001
    sex = VOICE_SEXES[controller._voice_sex_index]  # noqa: SLF001

    window = controller.window
    # The glyph is shown as an icon rather than button text: Qt centres an
    # icon geometrically, while text sits on the emoji font's lopsided
    # baseline and rides high in the circular ring. The text is still set
    # (an icon-only QToolButton does not display it) so the state stays
    # readable to tests and accessibility tooling.
    for button, glyph, tip in (
        (window.btn_voice_region, region[1], f"{region[2]} voices (click to change)"),
        (window.btn_voice_sex, sex[1], f"{sex[2]} voices (click to change)"),
    ):
        pm = emoji_cue_pixmap(glyph)
        button.setIcon(QIcon(pm))
        button.setIconSize(pm.size())
        button.setText(glyph)
        button.setToolTip(tip)


def refresh_voices(controller) -> None:
    """Fill the dropdown with the current region and sex combination.

    Nothing is auto-selected: the user's existing pick survives when it
    still matches the filter, otherwise the combo returns to its
    placeholder and awaits an explicit choice.
    """

    region = VOICE_REGIONS[controller._voice_region_index][0]  # noqa: SLF001
    sex = VOICE_SEXES[controller._voice_sex_index][0]  # noqa: SLF001

    previous = controller.window.voice_combo.currentData()

    voices = [
        v
        for v in controller.voice_service.list_profiles()
        if v.name != "system" and _matches_filter(v.name, region=region, sex=sex)
    ]
    voices.sort(key=lambda v: voice_label(v).casefold())
    controller._voices = voices  # noqa: SLF001

    combo = controller.window.voice_combo
    combo.clear()
    for v in voices:
        combo.addItem(voice_label(v), v.name)
    if not voices:
        combo.addItem("(no voices found)")

    names = [v.name for v in voices]
    if previous in names:
        combo.setCurrentIndex(names.index(previous))
    else:
        combo.setCurrentIndex(-1)
        # A toggle just cost the user their pick: re-raise the amber
        # choose-a-voice prompt exactly as a fresh book does, but only when
        # there is a book to voice and there was a pick to lose.
        if previous and book_is_loaded(controller):
            begin_attention(controller)

    _update_toggle_cues(controller)
    apply_picker_availability(controller)


def apply_picker_availability(controller) -> None:
    """Enable the picker only once there is a book to voice."""

    available = book_is_loaded(controller)
    for name in ("voice_combo", "btn_voice_sex", "btn_voice_region"):
        widget = getattr(controller.window, name, None)
        if widget is not None:
            widget.setEnabled(available)


def toggle_voice_sex(controller) -> None:
    controller._voice_sex_index = (  # noqa: SLF001
        controller._voice_sex_index + 1  # noqa: SLF001
    ) % len(VOICE_SEXES)
    refresh_voices(controller)


def cycle_voice_region(controller) -> None:
    controller._voice_region_index = (  # noqa: SLF001
        controller._voice_region_index + 1  # noqa: SLF001
    ) % len(VOICE_REGIONS)
    refresh_voices(controller)


class PickerAttention(QObject):
    """The amber ring asking the user to choose a voice.

    Flashes (property toggling on a two second cycle) until the user first
    touches the combo, stays steady until a voice is chosen, then clears.
    """

    def __init__(self, controller) -> None:
        super().__init__(controller.window.voice_combo)
        self._controller = controller
        self._flashing = False
        self._timer = QTimer(self)
        self._timer.setInterval(ATTENTION_FLASH_HALF_PERIOD_MS)
        self._timer.timeout.connect(self.tick)
        controller.window.voice_combo.installEventFilter(self)

    def _set_ring(self, on: bool) -> None:
        combo = self._controller.window.voice_combo
        combo.setProperty("attention", bool(on))
        combo.style().unpolish(combo)
        combo.style().polish(combo)

    def start(self) -> None:
        """Begin flashing; a no-op when a voice is already chosen."""

        if self._controller.window.voice_combo.currentData():
            return
        self._flashing = True
        self._set_ring(True)
        self._timer.start()

    def tick(self) -> None:
        combo = self._controller.window.voice_combo
        self._set_ring(not bool(combo.property("attention")))

    def steady(self) -> None:
        """Stop flashing but keep the ring until a voice is chosen."""

        self._flashing = False
        self._timer.stop()
        self._set_ring(True)

    def clear(self) -> None:
        self._flashing = False
        self._timer.stop()
        self._set_ring(False)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if self._flashing and event.type() in (
            QEvent.Enter,
            QEvent.FocusIn,
            QEvent.MouseButtonPress,
        ):
            self.steady()
        return False


def begin_attention(controller) -> None:
    """A book just landed: ask for a voice unless one is already chosen."""

    attention = getattr(controller, "_picker_attention", None)
    if attention is not None:
        attention.start()


def on_voice_selected(controller) -> None:
    """A combo selection changed: clear the prompt and pre-synthesise."""

    if not controller.window.voice_combo.currentData():
        return

    attention = getattr(controller, "_picker_attention", None)
    if attention is not None:
        attention.clear()

    if book_is_loaded(controller):
        from voice_reader.ui._ui_controller_book_loading import _start_presynthesis

        _start_presynthesis(controller)
