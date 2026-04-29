# Implementation Plan: feature/ns-w1-ispl-mcmas (PR6 of W1)

## Overview

Sixth PR of W1. Implements the offline ISPL (MCMAS) and SMV (NuSMV) text emitters
for `(Trace, agent_ids, formulae)`. Used by P1's offline soundness proofs and
the W6 ILP layer's MCMAS verification of induced protocols.

**Master plan acceptance criterion (§7 W1):** "ISPL emitter for MCMAS; offline
check on a 4-agent / 4-round example; verifies `EventuallyDecide` and
`RefutationReachable`."

## Architecture Decisions

- **Text-only emitters in `council/`**; subprocess invocation of MCMAS / NuSMV
  lives ONLY in `tests/integration/` (Constitution §8 — no system-tool calls
  from `council/`).
- **Encode the trace as a deterministic finite Kripke structure**: an `Environment`
  agent with a `position : 0..N` counter advances through each move; per-event
  atomic propositions are exposed in the `Evaluation` block.
- **LTL_f → CTL translation** for the Formulae block: `F(p) → EF(p)` (existential)
  or `AF(p)` (universal), `G(p) → AG(p)`. We default to the universal forms
  (`AF`, `AG`) since the trace is deterministic — both quantifiers coincide.
  Nested temporal: handled compositionally via the same translation.
- **No CTLK/ATL** in PR6: epistemic/strategic operators belong in T3 (PR9) where
  the encoding is wider. PR6 covers the propositional CTL fragment sufficient
  for `EventuallyDecide` and `RefutationReachable`.

## Tasks

### Task 1 — `council/symbolic/verify/ispl.py`

- `trace_to_ispl(trace, formulae, *, agent_ids) -> str`
- Internal helpers:
  - `_encode_environment_agent(trace) -> str` — single Environment agent with `position`
    state variable
  - `_encode_evaluations(trace) -> str` — per-position AP truth table
  - `_ltlf_to_ctl(formula: LTLf) -> str` — translate to MCMAS-compatible CTL syntax
  - `_format_init_states(...)`, `_format_formulae_section(...)`

### Task 2 — `council/symbolic/verify/smv.py`

- `trace_to_smv(trace, formulae) -> str` — NuSMV variant, simpler module syntax

### Task 3 — Tests

- `tests/symbolic/verify/test_ispl.py`:
  - Output contains required ISPL keywords (`Agent`, `end Agent`, `Vars:`,
    `Evolution:`, `Evaluation`, `InitStates`, `Formulae`)
  - Agent count matches input
  - Each event index produces an `Evaluation` clause
  - Formulae are translated to CTL syntax
- `tests/symbolic/verify/test_smv.py`:
  - Output contains `MODULE main`, `VAR`, `INIT`, `TRANS`, `SPEC`
  - Per-position state encoding
- `tests/integration/test_mcmas_offline.py` (gated by RUN_INTEGRATION=1
  AND `mcmas` on PATH):
  - 4-agent, 4-round trace: 1 Propose, 1 Challenge, 1 Concede, 1 Vote
  - Generate ISPL, run MCMAS, parse output, assert EventuallyDecide and
    RefutationReachable both verified

### Task 4 — Update `__init__.py` re-exports

Add `trace_to_ispl`, `trace_to_smv` to public surface.

## Final checkpoint

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all pass
- [ ] `uv run ruff check` — clean
- [ ] Generated ISPL passes structural validation
- [ ] (Optional, gated): MCMAS offline verification passes on 4-agent example

## Risks

| Risk | Mitigation |
|---|---|
| MCMAS rejects generated ISPL syntax | Validate against MCMAS user manual; structural tests for keywords |
| LTL_f → CTL translation lossy on temporal nesting | Document supported subset; raise NotImplementedError for unsupported |
| `Trace.to_events()` keys with dots/special chars break ISPL identifiers | Sanitise AP names to alphanumeric/underscore (current schema is safe) |
