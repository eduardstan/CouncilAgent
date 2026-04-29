# Implementation Plan: feature/ns-w1-ltlf-ast

## Overview

First PR of W1. Delivers two W0 micro-patches (derived APs on `to_events()`, `tool_client`
on `CouncilContext`) and the pure-Python LTL_f AST + parser that every subsequent W1 PR
compiles against. No external parser libraries. mypy strict throughout.

## Architecture Decisions

- **Patch A before AST**: `trace.py` and `context.py` changes have zero new dependencies and
  touch the most-tested W0 files — validate them first so the mypy baseline is confirmed clean.
- **Recursive-descent parser**: 9-node grammar fits in ~100 LOC. No lark/antlr — Constitution §8
  forbids framework deps in the core path.
- **`to_spot_str()` not `__str__()`**: keep `__str__()` for debugging (human-readable), expose
  `to_spot_str()` as the SPOT bridge so the two renderings can diverge if needed.
- **`same_agent_concede_run_ge_3` via prefix scan**: `to_events()` already iterates all moves;
  computing the concede-run requires a per-agent counter reset at each non-Concede move —
  O(n) single pass, no auxiliary data structure.

## Dependency graph

```
Patch A (trace.py)  ──┐
                       ├─→ test_trace_derived_aps.py
Patch B (context.py) ─┘       │
                               ↓
                        Checkpoint 1 (mypy + existing tests green)
                               │
                               ↓
                       ltlf.py (AST + parser)
                               │
                               ↓
                       test_ltlf.py (20+ round-trips)
                               │
                               ↓
                        Checkpoint 2 (full suite green)
                               │
                               ↓
                       ADR 0002
```

---

## Phase 1: W0 micro-patches

### Task 1 — Patch A: extend `to_events()` with derived APs

**Description:** Add three boolean fields to each event dict produced by `Trace.to_events()`.
Computation is a single forward pass over `self.moves` with per-agent running state for the
concede-run counter. Update the docstring.

**Acceptance criteria:**
- [ ] `has_evidence: bool` present on every event dict
- [ ] `has_prior_challenge: bool` present on every event dict
- [ ] `same_agent_concede_run_ge_3: bool` present on every event dict
- [ ] Existing `to_events()` keys unchanged
- [ ] Docstring updated: "extended in W1/PR1 — adds has_evidence, has_prior_challenge, same_agent_concede_run_ge_3"
- [ ] `uv run mypy council/dialect/trace.py` — 0 errors

**Verification:**
- [ ] `uv run mypy council/` exits 0
- [ ] `uv run pytest tests/dialect/` passes (no regressions)

**Dependencies:** None

**Files:** `council/dialect/trace.py`

**Scope:** XS

---

### Task 2 — Patch B: add `tool_client` to `CouncilContext`

**Description:** Add `tool_client: ToolClient | None = None` as a trailing optional field on the
`CouncilContext` frozen dataclass. Import `ToolClient` from `council.tools` (W0 stub already
exists). All existing call sites omit the field and get `None` by default — no callsite changes.

**Acceptance criteria:**
- [ ] `CouncilContext` has `tool_client: ToolClient | None = None`
- [ ] `from council.tools import ToolClient` added to `council/context.py`
- [ ] `uv run mypy council/` exits 0
- [ ] `uv run pytest tests/test_context.py` passes

**Verification:**
- [ ] `uv run mypy council/` exits 0
- [ ] `uv run pytest tests/` passes (no regressions)

**Dependencies:** None (parallel with Task 1, but commit after Task 1 for clean history)

**Files:** `council/context.py`

**Scope:** XS

---

### Checkpoint 1

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all existing tests pass (158 functions)
- [ ] Both patches committed on `feature/ns-w1-ltlf-ast`

---

## Phase 2: LTL_f AST

### Task 3 — Implement `council/symbolic/verify/ltlf.py`

**Description:** Pure-Python LTL_f AST with 9 node types and a recursive-descent parser.
Also expose `to_spot_str()` as the SPOT-compatible rendering (used by PR4 `spot_backend.py`).

Node types (all `frozen=True, slots=True` dataclasses):
- `Atom(name: str)` — atomic proposition
- `Neg(arg: LTLf)` — negation (`!` / `not`)
- `And(left, right)` — conjunction (`&&` / `&` / `and`)
- `Or(left, right)` — disjunction (`||` / `|` / `or`)
- `Next(arg)` — next operator (`X`)
- `Until(left, right)` — until (`U`)
- `Finally(arg)` — eventually (`F`) — sugar for `true U phi`
- `Globally(arg)` — globally (`G`) — sugar for `! F ! phi`
- `WeakUntil(left, right)` — weak until (`W`)

Parser operator precedence (low → high):
1. `U`, `W` (right-associative)
2. `||` / `or`
3. `&&` / `and`
4. `!` / `not` (prefix)
5. `X`, `F`, `G` (prefix)
6. atoms and `(...)` groups

**Acceptance criteria:**
- [ ] All 9 node types defined as frozen slots dataclasses inheriting `LTLf(ABC)`
- [ ] `parse(formula: str) -> LTLf` handles all 9 node types
- [ ] `to_spot_str(f: LTLf) -> str` round-trips: `to_spot_str(parse(s)) == to_spot_str(parse(to_spot_str(parse(s))))` for all test formulae
- [ ] `parse("")` or `parse("(")` raises `ValueError` with a descriptive message
- [ ] No imports beyond the standard library and `from __future__ import annotations`
- [ ] `uv run mypy council/symbolic/verify/ltlf.py` — 0 errors

**Verification:**
- [ ] `uv run mypy council/` exits 0
- [ ] (tests written in Task 4)

**Dependencies:** Task 1, Task 2 (Checkpoint 1 must be green)

**Files:** `council/symbolic/verify/ltlf.py`, `council/symbolic/verify/__init__.py` (add re-exports)

**Scope:** M (~120 LOC implementation)

---

### Task 4 — Tests: `test_ltlf.py` and `test_trace_derived_aps.py`

**Description:** Write the test files for the AST/parser and for the Patch A derived APs.
Also create `tests/symbolic/__init__.py` and `tests/symbolic/verify/__init__.py`.

`test_ltlf.py` must include:
- Round-trip idempotence: `assert parse(to_spot_str(parse(s))) == parse(s)` for 20+ formulae
  covering every node type and precedence edge cases
- `test_parse_error`: `pytest.raises(ValueError)` on `""`, `"("`, `"F"` (bare operator),
  `"A &&"` (incomplete)

`test_trace_derived_aps.py` must include:
- `test_has_evidence_true`: `Propose` with `evidence=("e1",)` → event has `has_evidence=True`
- `test_has_evidence_false`: `Propose` with `evidence=()` → event has `has_evidence=False`
- `test_has_evidence_vote`: `Vote` with non-empty `evidence` → `has_evidence=True`
- `test_has_prior_challenge_false`: trace with only Proposes → all events `has_prior_challenge=False`
- `test_has_prior_challenge_true`: trace with a Challenge at move 1 → moves 2+ have `has_prior_challenge=True`; move 0 and 1 have `has_prior_challenge=False`
- `test_same_agent_concede_run_ge_3_false`: two consecutive Concedes from same agent → `False`
- `test_same_agent_concede_run_ge_3_true`: three consecutive Concedes from same agent → third is `True`
- `test_same_agent_concede_run_reset`: Concede–Propose–Concede–Concede pattern from same agent → second run of 2 is `False` (reset after Propose)
- `test_different_agents_not_counted`: Concede from agent A, Concede from agent B, Concede from agent A → agent A's run is 1 (not 3)

**Acceptance criteria:**
- [ ] `tests/symbolic/__init__.py` created (empty)
- [ ] `tests/symbolic/verify/__init__.py` created (empty)
- [ ] `tests/symbolic/verify/test_ltlf.py` — ≥ 20 parametrized round-trip cases + 4 error cases
- [ ] `tests/symbolic/verify/test_trace_derived_aps.py` — 9 named test functions
- [ ] `uv run pytest tests/symbolic/verify/test_ltlf.py tests/symbolic/verify/test_trace_derived_aps.py` — all pass

**Verification:**
- [ ] `uv run pytest tests/` — full suite passes
- [ ] `uv run mypy council/` — 0 errors

**Dependencies:** Task 3

**Files:** 4 new files (2 `__init__.py`, 2 test files)

**Scope:** M (~120 LOC tests)

---

### Task 5 — Update `tests/test_context.py`

**Description:** Add one test verifying that `CouncilContext` constructs without supplying
`tool_client` (default is `None`) and one verifying that supplying a `ToolClient` instance
is accepted.

**Acceptance criteria:**
- [ ] `test_council_context_default_tool_client`: `ctx.tool_client is None`
- [ ] `test_council_context_with_tool_client`: pass a stub `ToolClient` subclass; `ctx.tool_client is stub`
- [ ] Existing `test_context.py` tests still pass

**Verification:**
- [ ] `uv run pytest tests/test_context.py` — all pass

**Dependencies:** Task 2

**Files:** `tests/test_context.py`

**Scope:** XS

---

### Checkpoint 2

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all tests pass (158 existing + new W1 tests)
- [ ] `uv run ruff check council/ tests/` — 0 warnings

---

## Phase 3: ADR

### Task 6 — Write ADR 0002: `to_events()` extension

**Description:** Document the architectural decision to extend `Trace.to_events()` with derived
boolean APs rather than approximating properties with the existing schema.

**Acceptance criteria:**
- [ ] `specs/adrs/0002-w1-to-events-extension.md` exists
- [ ] Contains: Status (Accepted), Context, Decision, Consequences, Alternatives considered

**Verification:**
- [ ] File is valid Markdown with all required sections

**Dependencies:** Task 4 (implementation complete so consequences are concrete)

**Files:** `specs/adrs/0002-w1-to-events-extension.md`

**Scope:** XS

---

### Final Checkpoint

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all tests pass
- [ ] `uv run ruff check council/ tests/` — 0 warnings
- [ ] Total diff ≤ 600 LOC
- [ ] All 6 tasks committed with descriptive messages on `feature/ns-w1-ltlf-ast`
- [ ] Ready for PR to `council-ns`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `same_agent_concede_run_ge_3` logic is off-by-one | Med | Table-driven tests with concrete traces including the reset case |
| `parse()` precedence wrong for `U`/`W` right-assoc | Med | Round-trip test `A U B U C` → verify right-assoc parse tree |
| mypy `slots=True` with ABC fails on some Python versions | Low | Tested against Python 3.11 in CI; use `from __future__ import annotations` |
| `ToolClient` import creates a circular import | Low | `council/tools.py` already imported nowhere in `context.py` — clean add |
