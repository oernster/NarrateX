# NarrateX: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `voice_reader` package, `app.py`, the bespoke installer, the delivery scripts and the narratex.co.uk site under `docs/`) read against `ARCHITECTURE.md`, `ARCHITECTURE_CONSTRAINTS.md`, `TESTING.md` and the tests under `tests/structural/`.

This project has the strongest structural enforcement in the portfolio: `tests/structural/` holds composition-root, layering, LOC and narration-contract tests, `test_loc_limits.py` carries an explicit build-script exemption list and the installer has its own test package. The debt below is measured against that standard, not against a lower one.

---

## 1. The icon set is hand-maintained and now exists in two places

`narratex.png` at repository root is the master, and the eight derived sizes (`narratex_16.png` through `narratex_512.png`) plus `narratex.ico` sit beside it. Nothing derives them: this is the only application in the portfolio with no `generate_icons.py`, so the set is maintained by hand and can drift from its own master without anything noticing.

Moving the site into `docs/` made that concrete rather than theoretical. GitHub Pages publishes `docs/` and nothing above it, so the five sizes the pages use as favicons and touch icons (16, 32, 64, 256 and 512) now exist twice: once at root for the application build and once under `docs/` for the site. They were copied rather than regenerated, deliberately, because regenerating the set inside a site move would have changed shipped icon bytes as a side effect of a directory change.

The fix is the portfolio's standard one: a `generate_icons.py` reading `narratex.png` and emitting every consumer's copy, root and `docs/` alike, so the duplication is generated rather than maintained. Until then the two copies are byte-identical and can silently stop being so.

## 2. Broad exception handlers on the startup path and in the installer

`app.py` has ten `except Exception` blocks with no `# noqa` and no comment, on the application's startup path. `installer/ops/` has around fifteen more across `install_ops.py`, `shortcuts.py`, `repair_ops.py` and `staging.py`, of which only two carry a `# noqa: BLE001`.

Startup and installation are the two paths where a swallowed exception produces the worst user experience available: an application that does not appear or a half-installed one with no error. Each handler should name what it degrades and why in one line and then narrow to the exception that actually occurs. `installer/ops/` is already Qt-free and already has a test package, so it can be done with tests rather than by inspection.

`app.py` also prints `"NarrateX: starting"` to stdout. It is a windowed application; the line goes nowhere a user will see and belongs behind the logger.

---

## Looks like debt, not worth touching

- `builddmg.py` at around 580 lines. Delivery script, exempt from the cap by design and correctly listed in `_BUILD_SCRIPTS` in the LOC test.
- The eleven files between 355 and 380 lines. All under the cap, all clear of the danger band, none needs anything.
- The `_ui_controller_*.py` and `_main_window_*.py` families and the thirteen-module `structural_bookmarks/` package. These are the 400-line cap doing its job; the parts are cohesive and merging any of them would breach it immediately.
- `voice_reader/ui/_ui_controller_ideas.py` and `ideas_dialog.py`, marked in `.coveragerc` as "Legacy Ideas UI (the brain button now uses Sections instead of Ideas)". Superseded UI that still loads. Worth deleting when someone is next in that area, not worth a dedicated pass.
- Four `requirements-*.txt` variants (base, linux, mac, flatpak). Native audio dependencies genuinely differ per platform; this is the documented split.
- `docs/site-images/NarrateX2.png`, a screenshot no page references any more. One stale binary, harmless where it sits; delete it next time the site images are touched.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **The em dashes in `navigation_chunk_service.py`, `structural_bookmarks/normalization.py`, `estimated_aligner.py`, `kokoro_engine.py` and `tests/domain/test_spoken_text_sanitizer.py`.** Every one is *data*: a character in a regex class, a replacement target or test input for a text sanitiser whose job is to turn punctuation into speech. `kokoro_engine.py` literally reads `text.replace("—", " - ")  # em dash`. These are load-bearing. Do not let a global prose purge touch them.
- **The `books/*` omit entry with its comment warning against `*/books/*`.** The comment records a real trap: the glob form would also match `voice_reader/infrastructure/books/*` and silently drop the shipped parser from the gate. Precise as written; the comment is why.
- **The audio, TTS and Qt omissions** (`sounddevice_streamer`, `_sounddevice_workers`, `_silence_trimmer`, `audio_streamer`, `kokoro_engine`, `tts_engine_factory` and the UI modules). Hardware devices, background threads and the Qt event loop. This is the documented, correct exclusion and nothing above asks for any of it back.
- **`app.py` sitting outside the coverage source.** The entrypoint wires the composition root to a real Qt application and a real audio device, so measuring it would measure the wiring and nothing else. It is left unnamed in `.coveragerc` rather than sourced and then omitted, so the file no longer needs a paragraph to defend itself.
- **The two unreachable lines in `estimated_aligner.py` and `chunking_service.py`.** Both are guards that cannot fire by construction (the aligner cannot fail to tokenise a stripped non-empty string; the sentence splitter cannot emit an empty part) and both say so in a comment. Deleting the guard to gain a covered line would remove the thing that makes the assumption explicit.
- **`tests/structural/test_loc_limits.py`'s `_BUILD_SCRIPTS` exemption set.** The clearest expression of the build-script rule anywhere in the portfolio and the reference other projects should copy.
- **`tests/structural/test_composition_roots.py` and `test_narration_contracts.py`.** A composition-root whitelist and a contract test for the narration seam. Both are the enforcement the rest of this file wishes existed elsewhere.
- **The separate `installer/ops` and `installer/ui` packages with their own test package.** Correct decomposition; item 2 is about the handlers inside it, not the shape.
