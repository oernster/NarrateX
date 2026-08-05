# Architecture constraints (hard-enforced)

This repo intentionally enforces a small set of structural constraints to keep the codebase maintainable as it grows.

These constraints are verified by the `tests/structural/*` suite and are intended to be **fast** and **fail-first**.

## 1) Layering rules (dependency direction)

The primary package is `voice_reader`, which is organized into layers:

- `voice_reader.shared`: lowest level helpers (logging/config/paths/runtime helpers). Must not import other `voice_reader.*` layers.
- `voice_reader.domain`: pure business logic + ports (protocols). Must not import other layers.
- `voice_reader.application`: orchestration; may depend on Domain (+ Shared).
- `voice_reader.infrastructure`: adapters that implement domain ports; may depend on Domain (+ Shared).
- `voice_reader.ui`: PySide UI; may depend on Application (+ Domain + Shared) but must not depend on Infrastructure.

Enforced by [`test_layering_rules_for_voice_reader_are_respected()`](tests/structural/test_layering_rules.py).

## 2) Composition roots (wiring policy)

"Wiring" (constructing concrete Infrastructure implementations and passing them into Application services) is only allowed in explicit **composition roots**.

In practice, composition roots are the only places allowed to import both:

- `voice_reader.application` **and**
- `voice_reader.infrastructure`

Enforced by [`test_only_composition_roots_may_import_both_application_and_infrastructure()`](tests/structural/test_composition_roots.py).

Current whitelist:

- [`app.py`](app.py) (primary runtime entrypoint)
- [`installer/app.py`](installer/app.py) (installer entrypoint)
- [`voice_reader/bootstrap.py`](voice_reader/bootstrap.py) (composition-root helper)
- [`voice_reader/book_load_worker.py`](voice_reader/book_load_worker.py) (the book-load child process's own composition root: it wires the parser, converter and cover extraction together with the chunk and chapter services inside the child)

Related: the packagers (`buildexe.py`, `buildlinux.py`, `builddmg.py`) are whitelisted importers of `voice_reader.bootstrap` because they derive their PyInstaller hidden-import lists from [`wiring_module_names()`](voice_reader/bootstrap.py) instead of mirroring the wiring table by hand; a mirrored list silently drifts and the frozen app then dies at startup with ModuleNotFoundError while the dev run works.

## 3) Module size guardrail

All in-scope `*.py` files must remain at most **400 physical lines**.

**Exempt: build and packaging scripts.** `buildexe.py`, `buildinstaller.py`, `builddmg.py`, `dmg_icon.py`, `build_utils.py`, `generate_icons.py`, `generate_scripts.py`, `stamp_version.py` and `installer/build_payload.py` are allowed to be large. They are linear recipes read top to bottom and splitting a sequence of flags and steps across modules costs more than it buys. The app package, the installer UI and the tests stay fully in scope.

Enforced by [`test_all_in_scope_python_files_are_at_most_400_lines()`](tests/structural/test_loc_limits.py).

This is a pragmatic guardrail to encourage extracting cohesive submodules and avoiding "god" modules.

**Refactoring rule (the 5% rule):** 400 is the limit and the normal target, so a file below it and clear of the band below needs nothing doing to it.

5% of 400 is 20, so **`>380` and `<400` (381 to 399) is the danger band. A file sitting in that band is reduced to <=350, never left at 399.** Both ways in are covered: a file that grew into the band and a file refactored down from over the cap, which must land at <=350 rather than stopping the moment it clears 400.

Trimming one or two lines to sit just under 400 buys nothing: the next edit breaks the cap again and the same file gets refactored over and over. Take a real reduction once instead, by extracting a cohesive module (a concern, not an arbitrary slice) or splitting a test file along its subject.

This applies to the file being edited and to any file the change pushes into that band and it applies to test files exactly as it does to source.

Enforced by [`test_no_in_scope_python_file_sits_in_the_danger_band()`](tests/structural/test_loc_limits.py), beside the cap assertion. The band is derived from the cap in the test rather than written as a second literal, so the two cannot drift apart. This is the constrain-the-bad-state form of the rule: the band cannot be entered rather than being noticed once a file is already sitting in it.

## 4) Narration is always built from a document model

Narration chunks come from the document model and from nowhere else. No caller may assemble chunks
ad hoc, because the model is the single answer to what a book contains and where; a second
construction path would be a second answer.

Enforced by [`test_every_build_chunks_call_supplies_a_document()`](tests/structural/test_narration_contracts.py).

## 5) One version string, in one file

[`VERSION`](VERSION) at the repository root is the single source of truth. Nothing else holds a
version literal:

- [`voice_reader/version.py`](voice_reader/version.py) reads it at import time, falling back to the
  obvious `0.0.0-dev` sentinel when the file is absent
- [`pyproject.toml`](pyproject.toml) declares `version = { file = "VERSION" }`
- the packagers ([`buildexe.py`](buildexe.py), [`buildinstaller.py`](buildinstaller.py),
  [`buildlinux.py`](buildlinux.py), [`builddmg.py`](builddmg.py),
  [`build_flatpak.sh`](build_flatpak.sh)) ship `VERSION` beside the package and read it through a
  `read_version()` helper carrying the same sentinel
- the published site pages, which cannot read a file at render time, carry delimited tokens
  refreshed from `VERSION` by [`stamp_version.py`](stamp_version.py). `buildexe.py` and
  `buildinstaller.py` call it before packaging, so the sweep is a build rule rather than a
  remembered step.

No tracked markdown file carries a version at all. `stamp_version.py` is deliberately scoped to
`docs/*.html`, the published site, so no markdown can acquire one by accident. It globs the
directory rather than naming pages, so adding a page does not mean remembering to list it.

Enforced by [`tests/test_version_source.py`](tests/test_version_source.py).

## 6) Icons: one master, everything derived

`narratex.png` is the only authored icon. The eight sizes the delivery scripts stage, the Windows
`narratex.ico` and the five copies the site needs under `docs/` are all emitted by
[`generate_icons.py`](generate_icons.py) and none is edited by hand. The site copies exist because
GitHub Pages publishes `docs/` and nothing above it, so the pages cannot reference the root set.

Every frame is a direct reduction of the master rather than a resize of a resize, which is what
keeps the 16 and 24 pixel sizes legible.

Enforced by [`tests/structural/test_icons_match_master.py`](tests/structural/test_icons_match_master.py),
which compares the whole set against a fresh render. `python generate_icons.py --check` performs
the same comparison without writing.

## Running the structural tests

The repo is configured to run pytest with a strict coverage gate by default (see pytest `addopts` in [`pyproject.toml`](pyproject.toml)).

When you run only `tests/structural`, those tests may not import runtime modules, which can cause coverage to report "no data" and fail the gate.

Use `--no-cov` when running the structural tests in isolation:

```bash
python -m pytest -q --no-cov tests/structural
```

On Windows if you use a project-local venv, prefer invoking via the venv Python:

```powershell
venv\Scripts\python.exe -m pytest -q --no-cov tests\structural
```

The full suite should still be run with coverage enabled:

```bash
python -m pytest -q
```


