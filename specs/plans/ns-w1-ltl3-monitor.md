# Implementation Plan: feature/ns-w1-ltl3-monitor (PR2 of W1)

## Overview

Second PR of W1. Delivers the `Verdict` enum, `LTL3Monitor` ABC, `Property` ABC, and
the `PurePythonLTL3Monitor` for the safety+reachability fragment of LTL_f. Operates
on event dicts produced by `Trace.to_events()` (Patch A from PR1).

PR3 (`ltl2mon-backend`) will add a `ProgressionMonitor` for the full LTL_f fragment;
both implement the `LTL3Monitor` ABC and PR3 cross-validates against PR2 on the
shared fragment. PR4 (`spot-backend`) adds `SPOTMonitor` and a `make_monitor()` factory.

## Architecture Decisions

- **`Verdict` is an `enum.Enum`**, not a string — type-safe and exhaustive in `match`.
- **TOP and BOTTOM are absorbing** at the outer monitor level. Once the verdict is
  non-`UNKNOWN`, `step()` short-circuits and returns the cached verdict.
- **PurePythonLTL3Monitor compiles to a tree of internal sub-monitors** (`_PropMonitor`,
  `_GloballyMonitor`, `_FinallyMonitor`, `_AndMonitor`, `_OrMonitor`). The compile
  step validates that the formula is in the safety+reachability fragment; nested
  temporal operators raise `ValueError` (PR3 handles them).
- **Three-valued combination operators** are AND-combined and OR-combined via the
  Kleene three-valued logic (BOTTOM-dominant for AND, TOP-dominant for OR, else UNKNOWN).
- **G never produces TOP at runtime** (would require certainty about all future events);
  **F never produces BOTTOM at runtime** (an extension could still satisfy it). This is
  the LTL3-over-infinite-extensions semantics.
- **Property ABC lives in monitor.py** (alongside LTL3Monitor) — concrete `Property`
  subclasses come in PR5 (`properties.py`).

## Supported fragment

| Shape | Example | Supported by PR2 |
|---|---|---|
| Propositional | `is_vote`, `!is_concede`, `is_propose && has_evidence` | ✅ |
| `G(propositional)` | `G(!is_concede)`, `G(is_propose -> has_evidence)` | ✅ |
| `F(propositional)` | `F(is_vote)`, `F(is_propose && is_challenge)` | ✅ |
| `And/Or of supported` | `G(p) && F(q)`, `G(p) \|\| F(q)` | ✅ |
| `X`, `U`, `W` | `X(p)`, `p U q` | ❌ — raise `ValueError`, see PR3 |
| Nested temporal | `G(F(p))`, `G(p -> F(q))` | ❌ — raise `ValueError`, see PR3 |

The named properties needing the unsupported fragment will use `ProgressionMonitor`
(PR3) when its registry is wired in PR5.

## Tasks

### Task 1 — `council/symbolic/verify/monitor.py`

- `Verdict(Enum)`: TOP, BOTTOM, UNKNOWN
- `LTL3Monitor(ABC)`: `step(event) -> Verdict`, `reset() -> None`, `current_verdict` property
- `Property(ABC)`: `name: ClassVar[str]`, `formula: ClassVar[str]`, `compile() -> LTL3Monitor`
- `_Compiled(ABC)`: internal sub-monitor base class with `step()` and `reset()`
- 5 concrete `_Compiled` subclasses
- `_compile(formula)` factory, `_is_propositional(formula)`, `_eval_prop(formula, event)` helpers
- `PurePythonLTL3Monitor(LTL3Monitor)`: top-level wrapper with absorbing-verdict cache

**Files:** `council/symbolic/verify/monitor.py` (new, ~200 LOC)
**Verification:** `uv run mypy council/` exits 0

### Task 2 — Tests

- `tests/symbolic/verify/test_monitor.py`:
  - Propositional: TOP at step 0 if true; BOTTOM at step 0 if false
  - `G(p)`: BOTTOM as soon as p false; UNKNOWN while p true; absorbing
  - `F(p)`: TOP as soon as p true; UNKNOWN while p false; absorbing
  - `And/Or` combinations
  - `reset()` restores UNKNOWN
  - Step after TOP returns TOP; step after BOTTOM returns BOTTOM
  - Unsupported formula raises ValueError (e.g., `X(p)`, `G(F(p))`, `p U q`)
  - Property ABC: subclass must declare name and formula and implement compile

**Files:** `tests/symbolic/verify/test_monitor.py` (new, ~200 LOC)
**Verification:** `uv run pytest tests/symbolic/verify/test_monitor.py` passes

### Task 3 — Update `__init__.py` re-exports

Re-export `Verdict`, `LTL3Monitor`, `Property`, `PurePythonLTL3Monitor` from
`council/symbolic/verify/__init__.py`.

### Final checkpoint

- [ ] `uv run mypy council/` exits 0
- [ ] `uv run pytest tests/` passes (all 245+ tests)
- [ ] `uv run ruff check council/ tests/` clean
- [ ] Branch ready to merge into council-ns

## Risks

| Risk | Mitigation |
|---|---|
| Three-valued combination logic wrong (Kleene) | Truth table tests for And/Or with all 9 verdict pairs |
| Absorbing semantics regression on reset() | Explicit reset test that re-runs the same trace and verifies fresh verdict |
| ValueError for nested temporal not raised early | Validation tests for G(F(.)), F(G(.)), p U q, X(p) |
