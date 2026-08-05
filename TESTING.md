# Testing workflow

This repo is intentionally test-first and gate-driven:

- `black` + `flake8` + `ruff` keep formatting/lint consistent.
- `pytest` runs with a strict **100% coverage** gate by default (see pytest `addopts` in [`pyproject.toml`](pyproject.toml)).
- Structural constraints are enforced by `tests/structural/*` (see [`ARCHITECTURE_CONSTRAINTS.md`](ARCHITECTURE_CONSTRAINTS.md)).

## Quick commands

Run the full suite (includes coverage gate):

```bash
python -m pytest -q
```

On Windows if you have a project-local venv, prefer invoking pytest via the venv Python to avoid accidentally running the global interpreter:

```powershell
venv\Scripts\python.exe -m pytest -q
```

Qt tests need an offscreen platform when running headless:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
```

The coverage table prints last and there is **no** "N passed" line under the
gate, so a substring search for `passed` or `failed` matches coverage filenames
rather than results. Read the exit code: `0` means every test passed **and** the
coverage gate was met.

Run lint (all three run clean from the repo root):

```bash
python -m black --check .
python -m flake8
python -m ruff check .
```

## Windows UI QA matrix (installer + app)

Some UI regressions only reproduce under Windows display scaling / accessibility
text sizing / mixed-DPI multi-monitor setups.

When validating a UI sizing/layout fix (especially the installer header in
[`InstallerMainWindow`](installer/ui/main_window.py)), test at least:

- Display scale: 100%, 125%, 150% (Windows Settings → System → Display)
- Accessibility → Text size: 100%, 110%+
- Single monitor vs 2+ monitors with *mixed* scale factors
- Move the window between monitors and confirm text remains un-clipped

Run *only* structural tests (without coverage, to avoid “no data collected” failures):

```bash
python -m pytest -q --no-cov tests/structural
```

## Coverage exclusions

Some modules are excluded from the 100% coverage gate because they depend on hardware, on threads or on a full TTS runtime that is unavailable in the standard dev environment. These are listed in [`.coveragerc`](.coveragerc) under `[run] omit`:

- `voice_reader/infrastructure/tts/kokoro_engine.py` - Kokoro TTS runtime (requires soundfile + torch)
- `voice_reader/infrastructure/tts/tts_engine_factory.py` - engine factory (same dependency)
- Audio, bookmark and preference adapters (threading plus hardware or filesystem I/O)
- The Qt layer: windows, dialogs and the controllers that drive them, which need an event loop and a live widget tree

`app.py` is not named in the source list at all. The entrypoint wires the composition root to a real Qt application and a real audio device, so measuring it would measure the wiring and nothing else.

The whole application layer is now inside the gate; so is the pure-domain layer. Narration orchestration (`application/services/narration/*` and `narration_service.py`) and structural bookmarks (`application/services/structural_bookmarks/*` and `structural_bookmark_service.py`) were both omitted for a time and both now sit at 100%. The three modules that own a thread's lifetime are covered by driving their own events rather than by sleeping: see [`tests/application/test_narration_synthesis_threads.py`](tests/application/test_narration_synthesis_threads.py), which scripts the stop and pause events so a worker halts at an exact line; and [`tests/application/test_narration_run.py`](tests/application/test_narration_run.py), which substitutes the run loop's collaborators at the module boundary. Two lines in the domain remain unreachable by construction and say so in a comment rather than being covered by a contrived test.

Matching test files that must be excluded from the pytest run (they will raise `collection errors` without the soundfile runtime):

```bash
python -m pytest --ignore=tests/infrastructure/test_filesystem_cache.py --ignore=tests/infrastructure/test_kokoro_engine_more_coverage.py --ignore=tests/infrastructure/tts --ignore=tests/application/test_tts_engine_factory.py --ignore=tests/application/test_tts_engine_factory_more_coverage.py
```

That is one line deliberately. A shell continuation is not portable between the shells this project
is developed in and a half-pasted command reads as a test failure rather than as a paste error.

## Test suite architecture

The test tree deliberately mirrors the four-layer clean architecture of the
production code (see [`ARCHITECTURE.md`](ARCHITECTURE.md)). Each directory under
`tests/` maps to a production concern and the isolation rules for each layer
match the dependency direction the layers themselves obey:

| Test directory | Mirrors | Design intent / isolation rule |
| --- | --- | --- |
| `tests/domain/` | `voice_reader.domain` | Pure business logic. Tests are pure and must not perform IO or import framework code. |
| `tests/application/` | `voice_reader.application` | Orchestration/services. Tests target the controller/service boundary; Infrastructure is stubbed. |
| `tests/infrastructure/` | `voice_reader.infrastructure` | Adapters implementing domain ports. External processes and heavy imports are stubbed. Sub-suites: `infrastructure/audio/`, `infrastructure/tts/`. |
| `tests/ui/` | `voice_reader.ui` | PySide UI. Tests assert controller behavior and signals, not brittle widget trees. Run under an offscreen Qt platform (see the `qapp` fixture in [`tests/conftest.py`](tests/conftest.py)). |
| `tests/shared/` | `voice_reader.shared` | Lowest-level helpers (logging/config/paths/runtime). |
| `tests/installer/` | `installer/` | Installer entrypoint and installer UI. |
| `tests/` (top level) | `app.py`, `voice_reader/bootstrap.py`, `voice_reader/book_load_worker.py`, `voice_reader/version.py` | Composition-root / entrypoint and process-boot behavior (app identity, icon fallback, preflight, book-load worker) plus the version single-source check. |
| `tests/structural/` | the codebase as a whole | AST/structural guards, not behavior. See below. |

Shared fixtures live in [`tests/conftest.py`](tests/conftest.py) - notably a
session-scoped offscreen `qapp` and an autouse per-test Qt-window cleanup, so UI
tests never leak windows or an event loop between cases.

### Structural tests (`tests/structural/`)

These enforce the architecture itself rather than any single behavior. They are
intended to be fast and fail-first and are documented in full in
[`ARCHITECTURE_CONSTRAINTS.md`](ARCHITECTURE_CONSTRAINTS.md):

- [`test_layering_rules.py`](tests/structural/test_layering_rules.py) - dependency direction between the layers (e.g. UI must not import Infrastructure; Domain imports nothing else).
- [`test_composition_roots.py`](tests/structural/test_composition_roots.py) - only whitelisted composition roots may import both Application and Infrastructure.
- [`test_loc_limits.py`](tests/structural/test_loc_limits.py) - the 400-line module-size guardrail (build/packaging scripts exempt), plus the 5% danger band: one assertion for the cap and a second for the 381 to 399 range, so a red run names which half was broken. The band is derived from the cap rather than written as a second literal.
- [`test_narration_contracts.py`](tests/structural/test_narration_contracts.py) - narration is always built from a document model (no ad-hoc chunk construction).
- [`test_icons_match_master.py`](tests/structural/test_icons_match_master.py) - every tracked icon matches a fresh render from the single master `narratex.png`, so no frame can be hand-edited out of step with the rest.

The version single-source rule is checked outside `tests/structural/` because it is a file-contents
assertion rather than an AST scan: see [`tests/test_version_source.py`](tests/test_version_source.py).

Because they may not import runtime modules, run them in isolation with
`--no-cov` to avoid a spurious "no data collected" coverage failure:

```bash
python -m pytest -q --no-cov tests/structural
```

## TDD approach used in this codebase

### 1) Prefer characterization tests for refactors

When changing internals (especially around narration orchestration and UI-controller semantics), start with a characterization test that captures observed behavior.

Examples of “behavior locks”:

- Narration orchestration: [`tests/application/test_narration_service.py`](tests/application/test_narration_service.py)
- UI semantics (non-brittle): [`tests/ui/test_ui_controller_play_pause_semantics.py`](tests/ui/test_ui_controller_play_pause_semantics.py)

Rule of thumb:

- If a bug report is “when I click X, Y should happen”, the test should target the controller/service boundary, not a pixel-perfect UI assertion.

### 2) Keep unit boundaries stable

- Domain tests should remain pure and not require IO.
- Infrastructure tests should stub external processes and heavy imports.
- UI tests should avoid brittle widget tree assertions where possible; focus on controller behavior and signals.

### 3) Small steps, always green

Recommended loop:

1. Write a failing test
2. Make the smallest change to pass
3. Refactor (extract module/class, reduce LOC, etc.)
4. Run `python -m pytest -q` to keep the coverage gate green

