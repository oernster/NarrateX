# Testing workflow

This repo is intentionally test-first and gate-driven:

- `black` + `flake8` keep formatting/lint consistent.
- `pytest` runs with a strict **100% coverage** gate by default (see pytest `addopts` in [`pyproject.toml`](pyproject.toml:1)).
- Structural constraints are enforced by `tests/structural/*` (see [`ARCHITECTURE_CONSTRAINTS.md`](ARCHITECTURE_CONSTRAINTS.md:1)).

## Quick commands

Run the full suite (includes coverage gate):

```bash
python -m pytest -q
```

Run lint:

```bash
python -m flake8
```

Run *only* structural tests (without coverage, to avoid “no data collected” failures):

```bash
python -m pytest -q --no-cov tests/structural
```

## TDD approach used in this codebase

### 1) Prefer characterization tests for refactors

When changing internals (especially around narration orchestration and UI-controller semantics), start with a characterization test that captures observed behavior.

Examples of “behavior locks”:

- Narration orchestration: [`tests/application/test_narration_service.py`](tests/application/test_narration_service.py:1)
- UI semantics (non-brittle): [`tests/ui/test_ui_controller_play_pause_semantics.py`](tests/ui/test_ui_controller_play_pause_semantics.py:1)

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

