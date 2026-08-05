# NarrateX: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `voice_reader` package, `app.py`, the bespoke installer, the delivery scripts and the narratex.co.uk site under `docs/`) read against `ARCHITECTURE.md`, `ARCHITECTURE_CONSTRAINTS.md`, `TESTING.md` and the tests under `tests/structural/`.

This project has the strongest structural enforcement in the portfolio: `tests/structural/` holds composition-root, layering, LOC and narration-contract tests, `test_loc_limits.py` carries an explicit build-script exemption list and the installer has its own test package. The debt below is measured against that standard, not against a lower one.

---

**There is no open technical debt.** The two sections below are the standing record of what was weighed and deliberately left alone, so the same ground is not covered again.

---

## Looks like debt, not worth touching

- `builddmg.py` at around 580 lines. Delivery script, exempt from the cap by design and correctly listed in `_BUILD_SCRIPTS` in the LOC test.
- The eleven files between 355 and 380 lines. All under the cap, all clear of the danger band, none needs anything.
- The `_ui_controller_*.py` and `_main_window_*.py` families and the thirteen-module `structural_bookmarks/` package. These are the 400-line cap doing its job; the parts are cohesive and merging any of them would breach it immediately.
- `voice_reader/ui/_ui_controller_ideas.py` and `ideas_dialog.py`, marked in `.coveragerc` as "Legacy Ideas UI (the brain button now uses Sections instead of Ideas)". Superseded UI that still loads. Worth deleting when someone is next in that area, not worth a dedicated pass.
- Four `requirements-*.txt` variants (base, linux, mac, flatpak). Native audio dependencies genuinely differ per platform; this is the documented split.
- `docs/site-images/NarrateX2.png`, a screenshot no page references any more. One stale binary, harmless where it sits; delete it next time the site images are touched.
- The master `narratex.png` being 487x487, which makes `narratex_512.png` a slight upscale. That is how the whole existing set was produced and `generate_icons.py` reproduces it exactly. Replacing the master with a 1024 render is an improvement to make deliberately, with the change to every derived asset visible in its own commit, rather than as a side effect of some other work.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **The em dashes in `navigation_chunk_service.py`, `structural_bookmarks/normalization.py`, `estimated_aligner.py`, `kokoro_engine.py` and `tests/domain/test_spoken_text_sanitizer.py`.** Every one is *data*: a character in a regex class, a replacement target or test input for a text sanitiser whose job is to turn punctuation into speech. `kokoro_engine.py` literally reads `text.replace("—", " - ")  # em dash`. These are load-bearing. Do not let a global prose purge touch them.
- **The `books/*` omit entry with its comment warning against `*/books/*`.** The comment records a real trap: the glob form would also match `voice_reader/infrastructure/books/*` and silently drop the shipped parser from the gate. Precise as written; the comment is why.
- **The audio, TTS and Qt omissions** (`sounddevice_streamer`, `_sounddevice_workers`, `_silence_trimmer`, `audio_streamer`, `kokoro_engine`, `tts_engine_factory` and the UI modules). Hardware devices, background threads and the Qt event loop. This is the documented, correct exclusion and nothing above asks for any of it back.
- **`app.py` sitting outside the coverage source.** The entrypoint wires the composition root to a real Qt application and a real audio device, so measuring it would measure the wiring and nothing else. It is left unnamed in `.coveragerc` rather than sourced and then omitted, so the file no longer needs a paragraph to defend itself.
- **The two unreachable lines in `estimated_aligner.py` and `chunking_service.py`.** Both are guards that cannot fire by construction (the aligner cannot fail to tokenise a stripped non-empty string; the sentence splitter cannot emit an empty part) and both say so in a comment. Deleting the guard to gain a covered line would remove the thing that makes the assumption explicit.
- **`tests/structural/test_loc_limits.py`'s `_BUILD_SCRIPTS` exemption set.** The clearest expression of the build-script rule anywhere in the portfolio and the reference other projects should copy.
- **`tests/structural/test_composition_roots.py` and `test_narration_contracts.py`.** A composition-root whitelist and a contract test for the narration seam. Both are the enforcement the rest of this file wishes existed elsewhere.
- **The separate `installer/ops` and `installer/ui` packages with their own test package.** Correct decomposition, and the reason the handlers inside it could be given stated reasons file by file.
