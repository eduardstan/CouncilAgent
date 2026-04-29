# Implementation Plan: feature/ns-w1-interventions (PR7 of W1)

## Overview

Seventh PR of W1. Implements the `Intervention` ABC and 5 concrete interventions
that materialise Constitution §12: "the verifier can intervene". When a monitor
returns `Verdict.BOTTOM`, the configured intervention executes before the next
deliberation round, redirecting deliberation rather than just observing it.

Per `architecture.md` approved exception 4: this is the only L1 module that
imports from `council/dialect/moves.py` to inject typed `Move`s on `⊥` verdicts.

## Architecture Decisions

- **Async `Intervention.execute()` signature**: matches the master plan §6.4
  contract `(trace, violated, ctx) -> Trace`. The contract returns a NEW trace
  (immutable Trace pattern, W0 invariant).
- **`agent_id` for injected moves**: synthetic moderator agent named
  `"_w1_intervention"` so injected moves are clearly identifiable in receipts
  and unambiguously not from a council member.
- **`round_index` of injected moves**: equal to the maximum existing round_index
  (the current round) so the intervention is part of the round it interrupts.
- **`move_id` of injected moves**: deterministic UUID derived from
  `(violated.name, len(trace.moves))` so that running the same (trace, property)
  pair twice yields the same intervention move IDs (testability).
- **`TriggerVerifier` no-op when `ctx.tool_client is None`**: graceful
  degradation — the intervention returns the unchanged trace and logs.
- **`EscalateModel` does NOT call generation models in PR7**: it injects an
  `Abstain` move from the offending agent and a placeholder `Propose` move
  (with a synthetic upgrade marker in the claim's `surface`). Real model
  escalation requires a `model_client.complete()` call which would only fire
  in PR8 once `LTLfMonitorTermination` provides the prompt context. For PR7,
  we keep `EscalateModel` deterministic and testable.
- **All 5 interventions are pure async functions on the trace**: no side
  effects beyond the returned `Trace`.

## The 5 Concrete Interventions

| Class | Effect | Move(s) injected |
|---|---|---|
| `ReprompCorrective` | Re-prompt the offending agent with the violation description | 1 `Question` move |
| `ForceChallenge` | Insert a Challenge from a devil's-advocate agent targeting the last Propose | 1 `Challenge` move |
| `TriggerVerifier` | Invoke `ctx.tool_client` to run a symbolic verifier; record result as Clarify | 1 `Clarify` move (or no-op if no `tool_client`) |
| `EscalateModel` | Mark the offending agent as Abstain; insert a placeholder upgraded-Propose | 1 `Abstain` + 1 `Propose` |
| `FreezeAndAccept` | No injection; trace returned unchanged | 0 moves |

## Tasks

### Task 1 — `council/symbolic/verify/interventions.py`

Implements `Intervention` ABC and the 5 classes. Each is a frozen dataclass
where applicable; classes with explicit instance state use a regular class.

### Task 2 — Tests

`tests/symbolic/verify/test_interventions.py`:
- Each Intervention subclass: at least one positive trace (returns expected
  delta) and one edge case (e.g., empty trace, no propose to challenge).
- `Intervention` is abstract — cannot be instantiated directly.
- `ForceChallenge` injects a Challenge whose `reason.surface` contains the
  violated property's name.
- `TriggerVerifier` no-op when `ctx.tool_client is None`.
- `FreezeAndAccept` returns the input trace unchanged (identity).

### Task 3 — Update `__init__.py` re-exports

## Final checkpoint

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all pass; ≥ 12 new tests
- [ ] `uv run ruff check` — clean

## Risks

| Risk | Mitigation |
|---|---|
| Injected moves break Trace.append invariants | Use the same Move dataclasses as W0; existing W0 tests catch type errors |
| `EscalateModel` requires model client → can't be tested with FakeModelClient | Defer real-model escalation to PR8; PR7 makes it deterministic |
| Synthetic agent_id "leaks" into council.agents tuple | Document as moderator-only; never added to ctx.agents |
