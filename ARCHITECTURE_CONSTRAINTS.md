# Architecture constraints (hard-enforced)

This repo intentionally enforces a small set of structural constraints to keep the codebase maintainable as it grows.

These constraints are verified by the `tests/structural/*` suite, and are intended to be **fast** and **fail-first**.

## 1) Layering rules (dependency direction)

The primary package is `voice_reader`, which is organized into layers:

- `voice_reader.shared`: lowest level helpers (logging/config/paths/runtime helpers). Must not import other `voice_reader.*` layers.
- `voice_reader.domain`: pure business logic + ports (protocols). Must not import other layers.
- `voice_reader.application`: orchestration; may depend on Domain (+ Shared).
- `voice_reader.infrastructure`: adapters that implement domain ports; may depend on Domain (+ Shared).
- `voice_reader.ui`: PySide UI; may depend on Application (+ Domain + Shared), but must not depend on Infrastructure.

Enforced by [`test_layering_rules_for_voice_reader_are_respected()`](tests/structural/test_layering_rules.py:111).

## 2) Composition roots (wiring policy)

"Wiring" (constructing concrete Infrastructure implementations and passing them into Application services) is only allowed in explicit **composition roots**.

In practice, composition roots are the only places allowed to import both:

- `voice_reader.application` **and**
- `voice_reader.infrastructure`

Enforced by [`test_only_composition_roots_may_import_both_application_and_infrastructure()`](tests/structural/test_composition_roots.py:93).

Current whitelist:

- [`app.py`](app.py:1) (primary runtime entrypoint)
- [`installer/app.py`](installer/app.py:1) (installer entrypoint)
- [`voice_reader/bootstrap.py`](voice_reader/bootstrap.py:1) (composition-root helper)

## 3) Module size guardrail

All in-scope `*.py` files must remain at most **400 physical lines**.

**Exempt: build and packaging scripts.** `buildexe.py`, `buildinstaller.py`, `builddmg.py`, `dmg_icon.py`, `build_utils.py`, `generate_icons.py`, `generate_scripts.py`, `stamp_version.py` and `installer/build_payload.py` are allowed to be large. They are linear recipes read top to bottom, and splitting a sequence of flags and steps across modules costs more than it buys. The app package, the installer UI and the tests stay fully in scope.

Enforced by [`test_all_in_scope_python_files_are_at_most_400_lines()`](tests/structural/test_loc_limits.py:61).

This is a pragmatic guardrail to encourage extracting cohesive submodules and avoiding "god" modules.

**Refactoring rule (the 5% rule):** 400 is the limit and the normal target, so a file below it and clear of the band below needs nothing doing to it.

5% of 400 is 20, so **`>380` and `<400` (381 to 399) is the danger band. A file sitting in that band is reduced to <=350, never left at 399.** Both ways in are covered: a file that grew into the band, and a file refactored down from over the cap, which must land at <=350 rather than stopping the moment it clears 400.

Trimming one or two lines to sit just under 400 buys nothing: the next edit breaks the cap again and the same file gets refactored over and over. Take a real reduction once instead, by extracting a cohesive module (a concern, not an arbitrary slice) or splitting a test file along its subject.

This applies to the file being edited and to any file the change pushes into that band, and it applies to test files exactly as it does to source.

## Running the structural tests

The repo is configured to run pytest with a strict coverage gate by default (see pytest `addopts` in [`pyproject.toml`](pyproject.toml:1)).

When you run only `tests/structural`, those tests may not import runtime modules, which can cause coverage to report "no data" and fail the gate.

Use `--no-cov` when running the structural tests in isolation:

```bash
python -m pytest -q --no-cov tests/structural
```

On Windows, if you use a project-local venv, prefer invoking via the venv Python:

```powershell
venv\Scripts\python.exe -m pytest -q --no-cov tests\structural
```

The full suite should still be run with coverage enabled:

```bash
python -m pytest -q
```


