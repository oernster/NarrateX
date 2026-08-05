# NarrateX: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `voice_reader` package, `app.py`, the bespoke installer, the delivery scripts and the narratex.co.uk site served from repository root) read against `ARCHITECTURE.md`, `ARCHITECTURE_CONSTRAINTS.md`, `TESTING.md` and the tests under `tests/structural/`.

This project has the strongest structural enforcement in the portfolio: `tests/structural/` holds composition-root, layering, LOC and narration-contract tests, `test_loc_limits.py` carries an explicit build-script exemption list and the installer has its own test package. The debt below is measured against that standard, not against a lower one.

---

## 1. The 100% gate omits both core service packages

`.coveragerc` still omits two entire application service packages:

- `voice_reader/application/services/narration_service.py` and `services/narration/*`
- `voice_reader/application/services/structural_bookmark_service.py` and `services/structural_bookmarks/*` (ten modules)

The stated reason is "not practical to exhaustively unit test (hardware/threads/Qt event loop)" and "heavily heuristic/regex-driven and covered via higher-level service tests". For the audio and TTS modules that is exactly right and they belong in the section below. It does not hold for the structural-bookmark package, which is demonstrably testable: `tests/application/test_structural_bookmark_service.py`, `test_structural_bookmark_service_axioms.py` and `test_structural_bookmark_duplicates.py` already test it. It is tested and then excluded from the gate, which means the gate cannot tell anyone whether that testing is still complete.

The result is that the headline claim (a 100% gate) stays silent about the modules that decide how a book is chunked into sections and how playback is orchestrated across them. That is the inverse of what a gate is for.

The proportionate fix, in order:

1. Remove `structural_bookmarks/*` and `structural_bookmark_service.py` from `omit` and let the existing tests carry as much as they carry, then close the remainder.
2. Leave `narration/*` omitted and say so explicitly with the thread and audio-device justification, rather than leaving it inside a general-purpose list.

The pure-domain half of this item is closed: `chunking_service.py`, `estimated_aligner.py` and `sanitized_text_mapper.py` are now inside the gate.

## 2. The `omit` list has accreted duplicates and a contradiction

Reading the same file top to bottom:

- `app.py` appears in `source =` and again in `omit =`, with a comment explaining the second. `--cov=app` in `addopts` is therefore inert. The intent (gate the package, not the entrypoint) is right; expressing it as source-plus-omit rather than just not sourcing it is confusing enough that the file needs a paragraph to defend it.
- `voice_reader/ui/_help_dialogs.py` is listed twice, once with forward slashes and once with backslashes.
- The comment "Windows path variants (coverage on win32 reports backslashes)" appears twice, heading two different blocks.
- Seven UI modules are each listed twice for the same reason.

None of this is wrong; all of it is the file telling you it has been edited under pressure. The backslash duplication in particular suggests the underlying problem was fought rather than solved: coverage path normalisation is configurable and one `[paths]` section would remove every backslash variant in the file.

Fixing item 1 means editing this list anyway. Do the tidy in the same pass.

## 3. The published site shares a directory with the application source

`index.html`, `why.html`, `download.html`, `styles.css`, `favicon.ico`, `robots.txt`, `sitemap.xml`, `site.webmanifest`, `CNAME` and `site-images/` all sit at repository root beside `app.py`, the build scripts and the package. Every other project in the portfolio publishes from `docs/`.

Nothing is broken by this and GitHub Pages supports it. The cost is that root has over forty tracked entries where the substance is one package and five build scripts. It also means no tool can distinguish "the site" from "the app" when reasoning about either. `stamp_version.py` currently works around it by naming the three site pages explicitly rather than globbing a directory, which is correct as written but is a workaround for the layout rather than a design.

Moving the site into `docs/` and pointing Pages at it is mechanical. `stamp_version.py` would then take a directory rather than a list.

## 4. The 5% danger band is documented and not enforced

`tests/structural/test_loc_limits.py` carries the rule in full as a comment block: 400 is the cap, 381 to 399 is the danger band, a file in the band goes to 350 or below rather than being shaved. The assertion then fails only above 400.

So the rule is written where a developer will read it and not where the build will apply it. No file is currently in the band (`voice_reader/ui/ui_controller.py` at 380 is the closest, one line away), which is the best possible moment to add the second assertion: fail over 400 and fail over 380 as well, so the band cannot be entered rather than being noticed after the fact. That is the constrain-the-bad-state form of the same rule.

## 5. Broad exception handlers on the startup path and in the installer

`app.py` has ten `except Exception` blocks with no `# noqa` and no comment, on the application's startup path. `installer/ops/` has around fifteen more across `install_ops.py`, `shortcuts.py`, `repair_ops.py` and `staging.py`, of which only two carry a `# noqa: BLE001`.

Startup and installation are the two paths where a swallowed exception produces the worst user experience available: an application that does not appear or a half-installed one with no error. Each handler should name what it degrades and why in one line and then narrow to the exception that actually occurs. `installer/ops/` is already Qt-free and already has a test package, so it can be done with tests rather than by inspection.

`app.py` also prints `"NarrateX: starting"` to stdout. It is a windowed application; the line goes nowhere a user will see and belongs behind the logger.

---

## Looks like debt, not worth touching

- `builddmg.py` at around 580 lines. Delivery script, exempt from the cap by design and correctly listed in `_BUILD_SCRIPTS` in the LOC test.
- The eleven files between 355 and 380 lines. All under the cap, all clear of the danger band, none needs anything.
- The `_ui_controller_*.py` and `_main_window_*.py` families and the ten-module `structural_bookmarks/` package. These are the 400-line cap doing its job; the parts are cohesive and merging any of them would breach it immediately.
- `voice_reader/ui/_ui_controller_ideas.py` and `ideas_dialog.py`, marked in `.coveragerc` as "Legacy Ideas UI (brain button now uses Sections instead of Ideas)". Superseded UI that still loads. Worth deleting when someone is next in that area, not worth a dedicated pass.
- Four `requirements-*.txt` variants (base, linux, mac, flatpak). Native audio dependencies genuinely differ per platform; this is the documented split.
- `site-images/NarrateX2.png`, a screenshot no page references any more. One stale binary, harmless where it sits; delete it next time the site images are touched.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **The em dashes in `navigation_chunk_service.py`, `structural_bookmarks/normalization.py`, `estimated_aligner.py`, `kokoro_engine.py` and `tests/domain/test_spoken_text_sanitizer.py`.** Every one is *data*: a character in a regex class, a replacement target or test input for a text sanitiser whose job is to turn punctuation into speech. `kokoro_engine.py` literally reads `text.replace("—", " - ")  # em dash`. These are load-bearing. Do not let a global prose purge touch them.
- **The `books/*` omit entry with its comment warning against `*/books/*`.** The comment records a real trap: the glob form would also match `voice_reader/infrastructure/books/*` and silently drop the shipped parser from the gate. Precise as written; the comment is why.
- **The audio, TTS and Qt omissions** (`sounddevice_streamer`, `_sounddevice_workers`, `_silence_trimmer`, `audio_streamer`, `kokoro_engine`, `tts_engine_factory` and the UI modules). Hardware devices, background threads and the Qt event loop. This is the documented, correct exclusion and item 1 does not ask for any of it back.
- **The two unreachable lines in `estimated_aligner.py` and `chunking_service.py`.** Both are guards that cannot fire by construction (the aligner cannot fail to tokenise a stripped non-empty string; the sentence splitter cannot emit an empty part) and both say so in a comment. Deleting the guard to gain a covered line would remove the thing that makes the assumption explicit.
- **`tests/structural/test_loc_limits.py`'s `_BUILD_SCRIPTS` exemption set.** The clearest expression of the build-script rule anywhere in the portfolio and the reference other projects should copy.
- **`tests/structural/test_composition_roots.py` and `test_narration_contracts.py`.** A composition-root whitelist and a contract test for the narration seam. Both are the enforcement the rest of this file wishes existed elsewhere.
- **The separate `installer/ops` and `installer/ui` packages with their own test package.** Correct decomposition; item 5 is about the handlers inside it, not the shape.
