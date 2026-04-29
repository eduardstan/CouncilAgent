# Implementation Plan: feature/ns-w1-ltlf-termination (PR8 of W1)

## Overview

Eighth PR of W1 — the most architecturally significant. Wires the L1 spine into
the `run_council()` pipeline:

1. `LTLfMonitorTermination` strategy that steps monitors per-round and reports
   violations (Constitution §12).
2. `core.run_council()` honours pending interventions before the next round, with
   a `max_interventions` bound (default 3) to prevent infinite loops.
3. `ProvenanceReceipt.monitor_verdicts` is populated whenever monitors are active.

## Architecture Decisions

- **`LTLfMonitorTermination` is a regular class with internal state**, not a
  frozen dataclass. It tracks the last stepped event index so each call to
  `should_stop()` only steps over new events.
- **Stop semantics**: returns `(True, property_name)` on `Verdict.BOTTOM` from
  any monitor. Returns `(False, "")` otherwise — including when all monitors
  return `Verdict.TOP` (other termination strategies decide whether to stop on
  satisfaction; this one only fires on violation).
- **Pending-intervention queue**: `LTLfMonitorTermination.pending_intervention()`
  returns the configured `Intervention` (single instance, not per-monitor) when a
  violation is current; consumed exactly once by `core.run_council()`.
- **`max_interventions` is on `LTLfMonitorTermination`**: default 3. After exhaustion,
  `should_stop()` returns `(True, "max-interventions-exhausted")` and the run ends.
- **Verdict tracking**: each call to `should_stop()` produces one `MonitorVerdict`
  per active monitor with its current verdict; `core.run_council()` collects these
  into `ProvenanceReceipt.monitor_verdicts`.
- **Backward compatibility**: when `termination` is not an `LTLfMonitorTermination`,
  no monitor wiring runs — `core.run_council()` works exactly as before.

## New Type: `MonitorVerdict`

```python
@dataclass(frozen=True, slots=True)
class MonitorVerdict:
    property_name: str    # e.g. "EventuallyDecide"
    verdict: str          # "top" / "bottom" / "unknown" (Verdict.value)
    round_index: int
```

Lives in `council/context.py` next to `ProvenanceReceipt`. The receipt's
`monitor_verdicts` field is narrowed from `tuple[object, ...]` to
`tuple[MonitorVerdict, ...]`.

## Tasks

### Task 1 — Add `MonitorVerdict` to `council/context.py`

- Define the dataclass
- Update `ProvenanceReceipt.monitor_verdicts: tuple[MonitorVerdict, ...]`
- Backward compatible: existing tests pass `()` as default

### Task 2 — Implement `LTLfMonitorTermination` in `council/termination.py`

- Import `Property`, `LTL3Monitor`, `Verdict`, `Intervention`
- Constructor: `(monitors: list[Property], on_violation: Intervention | None = None, max_interventions: int = 3)`
- Internal state: `_compiled: list[(Property, LTL3Monitor)]`, `_last_event_idx: int`,
  `_pending_intervention: Intervention | None`, `_intervention_count: int`,
  `_verdicts: list[MonitorVerdict]`
- `should_stop(trace, round_index)`: step monitors over new events; on BOTTOM
  set pending intervention; collect verdicts
- `pending_intervention() -> Intervention | None`: consumes the queued intervention
- `consume_verdicts() -> tuple[MonitorVerdict, ...]`: drain collected verdicts

### Task 3 — Wire `core.run_council()` intervention loop

- After `should_stop` returns True with a non-empty reason:
  - If termination is `LTLfMonitorTermination` and has a pending intervention:
    - Apply the intervention (await) — produces a new trace
    - Continue to next round
  - Else: break
- Drain monitor verdicts on every round; pass to receipt at the end
- Add type guard for `LTLfMonitorTermination` (don't break duck-typed strategies)

### Task 4 — Tests

`tests/symbolic/verify/test_ltlf_termination.py`:
- `LTLfMonitorTermination` with `EventuallyDecide`: trace without vote → UNKNOWN
- `LTLfMonitorTermination` with `NoSycophancyCascade`: 3 same-agent concedes →
  `should_stop` returns `(True, "NoSycophancyCascade")`; pending_intervention
  is the configured ForceChallenge
- `LTLfMonitorTermination` integrated into `CompositeTermination`
- `consume_verdicts()` drains the collected verdicts
- `max_interventions` exhaustion fires `(True, "max-interventions-exhausted")`

`tests/test_core.py` (extension, not a new file):
- End-to-end `run_council()` test with `FakeModelClient` returning Vote moves
  on every step + active `EventuallyDecide` monitor → receipt.monitor_verdicts
  is non-empty
- End-to-end test with a trace that violates `NoPrematureConsensus`: the
  configured ForceChallenge intervention fires; max-3 cap prevents infinite loop

### Task 5 — Update `__init__.py` re-exports

`MonitorVerdict` from `council.context`; `LTLfMonitorTermination` from
`council.termination`.

## Final checkpoint

- [ ] `uv run mypy council/` — 0 errors
- [ ] `uv run pytest tests/` — all pass
- [ ] `uv run ruff check` — clean
- [ ] End-to-end test: `ProvenanceReceipt.monitor_verdicts` non-empty when monitor active

## Risks

| Risk | Mitigation |
|---|---|
| Infinite intervention loop | `max_interventions=3` cap; tested explicitly |
| W0 callsites break when termination type widens | Type guard `isinstance(termination, LTLfMonitorTermination)` |
| Intervention modifies trace mid-iteration | Trace is immutable; intervention returns new trace; assigned to local |
| Receipt typing change cascades into existing tests | `tuple[MonitorVerdict, ...]` accepts `()` — same default; no callsite changes |
