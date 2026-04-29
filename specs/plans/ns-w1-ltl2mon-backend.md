# Implementation Plan: feature/ns-w1-ltl2mon-backend (PR3 of W1)

## Overview

Third PR of W1. Implements the progression-based `ProgressionMonitor` for the
**full** LTL_f fragment: atoms, Boolean combinations, X, F, G, U, W, and any
nesting thereof. This is the "full LTL_f" pure-Python fallback that runs
without SPOT.

Algorithm: Bauer 2010 progression. Maintains the formula as a residual that
is rewritten on every event. When the residual simplifies to `TRUE` → TOP;
when it simplifies to `FALSE` → BOTTOM; otherwise UNKNOWN.

## Architecture Decisions

- **Add `Boolean(value: bool)` to `ltlf.py`** — Boolean constants are part of
  the natural LTL_f algebra and the only sane residual for tautologies. The
  parser does not produce `Boolean` nodes (no surface syntax for it); they
  appear only as progression residuals.
- **Simplification is conservative** — we apply identity laws (`TRUE ∧ φ = φ`,
  etc.) and complementarity (`φ ∧ ¬φ = FALSE`, `φ ∨ ¬φ = TRUE`) but do not
  attempt full Boolean SAT. Hand-crafted property formulae are simple enough.
- **Cross-validate with PR2** — for every formula in the safety+reachability
  fragment, the `ProgressionMonitor` and `PurePythonLTL3Monitor` must agree
  step-by-step on the same trace. This is a parametrised cross-validation test.

## Tasks

### Task 1 — Extend `ltlf.py` with Boolean constants

- `Boolean(LTLf)` frozen-slots dataclass with `value: bool` field
- `to_spot_str(Boolean)` → `"1"` / `"0"` (SPOT syntax)
- `__str__` → `"TRUE"` / `"FALSE"`
- Add tests to `test_ltlf.py`

### Task 2 — Implement `council/symbolic/verify/ltl2mon_backend.py`

- Module-level constants `TRUE = Boolean(True)`, `FALSE = Boolean(False)`
- `simplify(f: LTLf) -> LTLf` — recursive, applies identity and complementarity laws
- `progression(f: LTLf, event: dict[str, object]) -> LTLf` — Bauer 2010 rules
- `ProgressionMonitor(LTL3Monitor)` — wraps progression+simplify+verdict-extraction
- `_verdict_of(residual: LTLf) -> Verdict` — TOP if residual is `Boolean(True)`,
  BOTTOM if `Boolean(False)`, else UNKNOWN

### Task 3 — Tests

- `tests/symbolic/verify/test_ltl2mon_backend.py`:
  - simplify identity laws, complementarity, double-negation
  - progression correctness for atoms, booleans, X, U, W, F, G
  - nested temporal formulas: `G(p -> F(q))`, `F(G(p))`, `(p U q) U r`
  - Cross-validation with `PurePythonLTL3Monitor` on safety+reachability formulas
    (parametrised over a representative trace and a list of formulas)
  - Absorbing semantics, reset()

### Task 4 — Update `__init__.py` re-exports

Add `Boolean`, `ProgressionMonitor`, `progression`, `simplify` to the verify
package's public surface.

## Final checkpoint

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all pass
- [ ] `uv run ruff check` — clean
- [ ] Cross-validation: ProgressionMonitor agrees with PurePythonLTL3Monitor on the
      safety+reachability fragment for ≥ 5 representative formulas + 5 representative traces

## Risks

| Risk | Mitigation |
|---|---|
| Simplifier loses tautologies (`φ ∧ ¬φ ≠ FALSE`) | Use structural equality + canonical-order terms; test specific cases |
| Residual grows unboundedly across events | Memoise/canonicalise; test that 100-step trace doesn't OOM |
| Cross-validation diverges on edge cases | Parametrise over many trace/formula combinations |
| Bauer progression rules wrong for `W` | Cite Bauer 2010 in code comments; test against pen-and-paper derivations |
