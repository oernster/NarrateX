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

Enforced by [`test_all_in_scope_python_files_are_at_most_400_lines()`](tests/structural/test_loc_limits.py:61).

This is a pragmatic guardrail to encourage extracting cohesive submodules and avoiding "god" modules.

## Running the structural tests

The repo is configured to run pytest with a strict coverage gate by default (see pytest `addopts` in [`pyproject.toml`](pyproject.toml:1)).

When you run only `tests/structural`, those tests may not import runtime modules, which can cause coverage to report "no data" and fail the gate.

Use `--no-cov` when running the structural tests in isolation:

```bash
python -m pytest -q --no-cov tests/structural
```

The full suite should still be run with coverage enabled:

```bash
python -m pytest -q
```


